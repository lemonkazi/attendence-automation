from flask import Flask, request, jsonify
from flask_cors import CORS
from enum import Enum
import speech_recognition as sr
from pydub import AudioSegment
import tempfile
import os
import uvicorn
from typing import Dict, Any, Optional
import logging
from abc import ABC, abstractmethod
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz
from werkzeug.utils import secure_filename

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# --- Transcription Engine ---
class TranscriptionEngine(Enum):
    GOOGLE_WEB_SPEECH = "google_web_speech"
    VOSK = "vosk"
    WHISPER = "whisper"
    SPHINX = "sphinx"

class TranscriptionConfig:
    """Configuration for transcription services"""
    def __init__(self):
        # Read the environment variable, default to True if not set
        self.enable_whisper = os.getenv("ENABLE_WHISPER", "True").lower() in ("true", "1", "yes")
        self.preferred_engines = []
        if self.enable_whisper:
            self.preferred_engines.append(TranscriptionEngine.WHISPER)
        self.preferred_engines.extend([
            TranscriptionEngine.VOSK,
            TranscriptionEngine.GOOGLE_WEB_SPEECH,
        ])
        # self.preferred_engines = [
        #     TranscriptionEngine.VOSK,  # Offline, good balance
        #     TranscriptionEngine.WHISPER,  # High accuracy
        #     TranscriptionEngine.GOOGLE_WEB_SPEECH,  # Fallback
        # ]
        self.max_audio_length = 300  # 5 minutes
        self.sample_rate = 16000

class TranscriptionResult:
    """Standardized result format"""
    def __init__(self, text: str, engine: TranscriptionEngine, confidence: float = 1.0, success: bool = True):
        self.text = text
        self.engine = engine
        self.confidence = confidence
        self.success = success

class TranscriptionEngineInterface(ABC):
    """Interface for transcription engines"""
    
    @abstractmethod
    def transcribe(self, audio_path: str) -> TranscriptionResult:
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        pass

class GoogleWebSpeechEngine(TranscriptionEngineInterface):
    def __init__(self):
        self.recognizer = sr.Recognizer()
    
    def is_available(self) -> bool:
        return True  # Always available
    
    def transcribe(self, audio_path: str) -> TranscriptionResult:
        try:
            with sr.AudioFile(audio_path) as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio_data = self.recognizer.record(source)
                text = self.recognizer.recognize_google(audio_data)
                return TranscriptionResult(text, TranscriptionEngine.GOOGLE_WEB_SPEECH)
        except sr.UnknownValueError:
            return TranscriptionResult("", TranscriptionEngine.GOOGLE_WEB_SPEECH, success=True)
        except Exception as e:
            logger.error(f"Google Web Speech error: {e}")
            raise

class VoskEngine(TranscriptionEngineInterface):
    def __init__(self):
        self.model_path = None
        self._model = None
        self._initialize_vosk()
    
    def _initialize_vosk(self):
        """Initialize Vosk with a lightweight model"""
        try:
            from vosk import Model, KaldiRecognizer
            # Download model to ./models/vosk-model-small-en-us-0.15 if not exists
            model_path = "./models/vosk-model-small-en-us-0.15"
            if not os.path.exists(model_path):
                logger.warning("Vosk model not found. Please download from https://alphacephei.com/vosk/models")
                return
            self._model = Model(model_path)
            self.model_path = model_path
        except ImportError:
            logger.warning("Vosk not installed. Run: pip install vosk")
        except Exception as e:
            logger.error(f"Vosk initialization error: {e}")
    
    def is_available(self) -> bool:
        return self._model is not None
    
    def transcribe(self, audio_path: str) -> TranscriptionResult:
        if not self.is_available():
            raise RuntimeError("Vosk engine not available")
        
        try:
            import wave
            from vosk import KaldiRecognizer
            
            with wave.open(audio_path, "rb") as wf:
                # Check audio format
                if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getcomptype() != "NONE":
                    raise ValueError("Audio file must be WAV format mono PCM")
                
                recognizer = KaldiRecognizer(self._model, wf.getframerate())
                recognizer.SetWords(True)
                
                results = []
                while True:
                    data = wf.readframes(4000)
                    if len(data) == 0:
                        break
                    if recognizer.AcceptWaveform(data):
                        result = json.loads(recognizer.Result())
                        results.append(result.get("text", ""))
                
                # Get final result
                final_result = json.loads(recognizer.FinalResult())
                results.append(final_result.get("text", ""))
                
                text = " ".join(filter(None, results)).strip()
                return TranscriptionResult(text, TranscriptionEngine.VOSK)
                
        except Exception as e:
            logger.error(f"Vosk transcription error: {e}")
            raise

class WhisperEngine(TranscriptionEngineInterface):
    def __init__(self):
        self._model = None
        self._initialize_whisper()
    
    def _initialize_whisper(self):
        """Initialize Whisper with a small model for low resource usage"""
        try:
            import whisper
            # Use tiny or base model for low resource usage
            self._model = whisper.load_model("base")
        except ImportError:
            logger.warning("Whisper not installed. Run: pip install openai-whisper")
        except Exception as e:
            logger.error(f"Whisper initialization error: {e}")
    
    def is_available(self) -> bool:
        return self._model is not None
    
    def transcribe(self, audio_path: str) -> TranscriptionResult:
        if not self.is_available():
            raise RuntimeError("Whisper engine not available")
        
        try:
            result = self._model.transcribe(audio_path)
            text = result["text"].strip()
            return TranscriptionResult(text, TranscriptionEngine.WHISPER)
        except Exception as e:
            logger.error(f"Whisper transcription error: {e}")
            raise

class SphinxEngine(TranscriptionEngineInterface):
    def __init__(self):
        self.recognizer = sr.Recognizer()
    
    def is_available(self) -> bool:
        return True  # Always available with speech_recognition
    
    def transcribe(self, audio_path: str) -> TranscriptionResult:
        try:
            with sr.AudioFile(audio_path) as source:
                audio_data = self.recognizer.record(source)
                text = self.recognizer.recognize_sphinx(audio_data)
                return TranscriptionResult(text, TranscriptionEngine.SPHINX)
        except sr.UnknownValueError:
            return TranscriptionResult("", TranscriptionEngine.SPHINX, success=True)
        except Exception as e:
            logger.error(f"Sphinx transcription error: {e}")
            raise

class TranscriptionService:
    """Orchestrates multiple transcription engines with fallback"""
    
    def __init__(self, config: TranscriptionConfig):
        self.config = config
        self.engines = {
            TranscriptionEngine.GOOGLE_WEB_SPEECH: GoogleWebSpeechEngine(),
            TranscriptionEngine.VOSK: VoskEngine(),
            TranscriptionEngine.WHISPER: WhisperEngine(),
            TranscriptionEngine.SPHINX: SphinxEngine(),
        }
    
    def transcribe_audio(self, audio_path: str, preferred_engine: Optional[TranscriptionEngine] = None) -> Dict[str, Any]:
        """Transcribe audio using available engines with fallback"""
        
        engines_to_try = [preferred_engine] if preferred_engine else self.config.preferred_engines
        
        for engine_type in engines_to_try:
            engine = self.engines.get(engine_type)
            if engine and engine.is_available():
                try:
                    logger.info(f"Attempting transcription with {engine_type.value}")
                    result = engine.transcribe(audio_path)
                    
                    if result.text and len(result.text.strip()) > 0:
                        return {
                            "success": True,
                            "text": result.text,
                            "engine": result.engine.value,
                            "message": f"Transcription completed successfully using {result.engine.value}"
                        }
                    else:
                        logger.info(f"{engine_type.value} returned empty transcription")
                        
                except Exception as e:
                    logger.warning(f"{engine_type.value} failed: {e}")
                    continue
        
        # All engines failed or returned empty results
        return {
            "success": False,
            "text": "",
            "engine": "none",
            "message": "All transcription engines failed or returned empty results"
        }

# --- Google Sheets Auth ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
script_dir = os.path.dirname(os.path.abspath(__file__))
credential_path = os.path.join(script_dir, 'credential.json')
creds = ServiceAccountCredentials.from_json_keyfile_name(credential_path, scope)
client = gspread.authorize(creds)

# Get today's date
now = datetime.today()
month_str = now.strftime("%B")
year_last_two_digits = now.year % 100
worksheet_name = f"{month_str}{year_last_two_digits}"
sheet = client.open("Monthly Attendance Sheet").worksheet(worksheet_name)
today = datetime.today().strftime("%-m/%-d/%Y")

# --- Settings ---
employee_names = ["Abdullah Al Mamun", "Md. Nazmul Hasan", "Md. Majharul Anwar"]
tz = pytz.timezone("Asia/Dhaka")

# --- Refactored Function for Updating Attendance ---
def update_attendance(employee: str, date_str: str, column_name: str, time_str: str) -> bool:
    all_rows = sheet.get_all_values()
    headers = [h.strip() for h in all_rows[6]]
    headers_lower = [h.lower() for h in headers]
    try:
        name_col = headers_lower.index("name") + 1
        date_col = headers_lower.index("date") + 1
        target_col = headers_lower.index(column_name.lower()) + 1
        checkin_col = headers_lower.index("check-in") + 1
        checkout_col = headers_lower.index("check-out") + 1
        hours_logged_col = headers_lower.index("hours logged") + 1
        over_time_col = headers_lower.index("over time(h.m)") + 1
        attendance_status_col = headers_lower.index("attendance status") + 1
    except ValueError as e:
        return False
    last_date = None
    date_found = False
    empty_employee_row_idx = None
    for idx, row in enumerate(all_rows[7:], start=8):
        row_name = (row[name_col - 1] or "").strip()
        row_date_str = (row[date_col - 1] or "").strip()
        if not row_date_str and last_date is not None:
            row_date_str = last_date
        if row_date_str:
            last_date = row_date_str
        if row_date_str == date_str and not row_name:
            empty_employee_row_idx = idx
            continue
        if last_date == date_str and row_name == employee:
            sheet.update_cell(idx, target_col, time_str)
            date_found = True
            if column_name.lower() == "check-out":
                checkin_time_str = row[checkin_col - 1]
                if checkin_time_str:
                    try:
                        checkin_time = datetime.strptime(checkin_time_str, "%I:%M:%S %p")
                        checkout_time = datetime.strptime(time_str, "%I:%M %p")
                        hours_logged = (checkout_time - checkin_time).total_seconds() / 3600
                        over_time = hours_logged - 8.0
                        sheet.update_cell(idx, hours_logged_col, f"{hours_logged:.2f}")
                        sheet.update_cell(idx, over_time_col, f"{over_time:.2f}")
                        sheet.update_cell(idx, attendance_status_col, "Present")
                    except ValueError:
                        return False
                else:
                    return False
            return True
    if empty_employee_row_idx is not None:
        sheet.update_cell(empty_employee_row_idx, name_col, employee)
        sheet.update_cell(empty_employee_row_idx, target_col, time_str)
        sheet.update_cell(empty_employee_row_idx, hours_logged_col, "0.00")
        sheet.update_cell(empty_employee_row_idx, over_time_col, "0.00")
        sheet.update_cell(empty_employee_row_idx, attendance_status_col, "Present")
        return True
    if not date_found:
        insert_row_idx = idx + 1 if last_date is not None else 8
        new_row = [""] * len(headers)
        new_row[name_col - 1] = employee
        new_row[date_col - 1] = date_str
        new_row[hours_logged_col - 1] = "0.00"
        new_row[over_time_col - 1] = "0.00"
        new_row[attendance_status_col - 1] = "Present"
        if column_name.lower() == "check-in":
            new_row[checkin_col - 1] = time_str
        elif column_name.lower() == "check-out":
            new_row[checkout_col - 1] = time_str
        sheet.insert_row(new_row, insert_row_idx)
        return True
    return False

# --- Helper Functions ---
def convert_to_wav(input_path: str, output_path: str = None) -> str:
    """Convert any audio format to WAV for speech recognition"""
    if output_path is None:
        output_path = tempfile.mktemp(suffix='.wav')
    
    audio = AudioSegment.from_file(input_path)
    audio = audio.set_frame_rate(16000).set_channels(1)
    audio.export(output_path, format="wav")
    return output_path

def cleanup_files(*file_paths):
    """Clean up temporary files"""
    for file_path in file_paths:
        if file_path and os.path.exists(file_path):
            try:
                os.unlink(file_path)
            except Exception as e:
                logger.warning(f"Failed to delete {file_path}: {e}")

# --- Initialize Services ---
config = TranscriptionConfig()
transcription_service = TranscriptionService(config)

# --- Routes ---
@app.route('/', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "message": "Attendance and Transcription API is running"})

@app.route('/attendance', methods=['POST'])
def handle_attendance():
    data = request.get_json()
    employee = data.get('employee')
    action = data.get('action')
    date_str = data.get('date')
    time_str = data.get('time')
    if not all([employee, action, date_str, time_str]):
        return jsonify({'error': 'Missing data'}), 400
    column_name = 'check-in' if action == 'checkin' else 'check-out'
    if update_attendance(employee, date_str, column_name, time_str):
        return jsonify({'message': f'Successfully {action} for {employee}'})
    else:
        return jsonify({'error': 'Failed to update attendance'}), 500

@app.route('/transcribe', methods=['POST'])
def transcribe_audio():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400
    allowed_extensions = ['.mp3', '.wav', '.webm', '.ogg', '.m4a', '.mp4', '.flac', '.mpeg']
    file_extension = os.path.splitext(file.filename.lower())[1]
    if file_extension not in allowed_extensions:
        return jsonify({'error': f"Unsupported file type. Supported formats: MP3, WAV, WebM, OGG, M4A, MP4, FLAC"}), 400
    input_path = None
    wav_path = None
    try:
        input_path = tempfile.mktemp(suffix=file_extension)
        file.save(input_path)
        wav_path = convert_to_wav(input_path)
        engine = request.form.get('engine', None)
        preferred_engine = TranscriptionEngine(engine) if engine else None
        result = transcription_service.transcribe_audio(wav_path, preferred_engine)
        result.update({"file_name": file.filename})
        return jsonify(result)
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return jsonify({'error': f"Transcription failed: {str(e)}"}), 500
    finally:
        cleanup_files(input_path, wav_path)

@app.route('/engines/status', methods=['GET'])
def get_engine_status():
    status = {}
    for engine_type, engine in transcription_service.engines.items():
        # For Whisper, also report if it was disabled by the feature flag
        if engine_type == TranscriptionEngine.WHISPER and not config.enable_whisper:
            status[engine_type.value] = {
                "available": False,
                "description": "Manually disabled via ENABLE_WHISPER environment variable"
            }
        else:
            status[engine_type.value] = {
                "available": engine.is_available(),
                "description": engine_type.name
            }
    return jsonify(status)

@app.route('/health', methods=['GET'])
def detailed_health_check():
    """Detailed health check"""
    engine_status = get_engine_status().get_json()
    return jsonify({
        "status": "healthy",
        "supported_formats": ["MP3", "WAV", "WebM", "OGG", "M4A", "MP4", "FLAC"],
        "engines": engine_status,
        "note": "FFmpeg required for non-WAV formats"
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8502, debug=True)
