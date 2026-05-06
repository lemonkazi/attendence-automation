from flask import Flask, request, jsonify
from flask_cors import CORS
from enum import Enum
# for production development
# from .assemblyai_engine import AssemblyAIEngine
# from .transcription_base import TranscriptionEngine, TranscriptionResult, TranscriptionEngineInterface
from assemblyai_engine import AssemblyAIEngine
from transcription_base import TranscriptionEngine, TranscriptionResult, TranscriptionEngineInterface

import speech_recognition as sr
from pydub import AudioSegment
import tempfile
import os
from typing import Dict, Any, Optional
import logging
from abc import ABC, abstractmethod
import json
import sys
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz
from werkzeug.utils import secure_filename

# Configure logging - ensure all logs are visible (no buffering)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# --- Transcription Config ---
class TranscriptionConfig:
    """Configuration for transcription services"""
    def __init__(self):
        # Read the environment variable, default to True if not set
        self.enable_whisper = os.getenv("ENABLE_WHISPER", "True").lower() in ("true", "1", "yes")
        self.preferred_engines = []
        # if self.enable_whisper:
        #     self.preferred_engines.append(TranscriptionEngine.WHISPER)
        self.preferred_engines.extend([
            TranscriptionEngine.ASSEMBLYAI,
            TranscriptionEngine.VOSK,
            TranscriptionEngine.GOOGLE_WEB_SPEECH,
        ])
        # self.preferred_engines.extend([
        #     TranscriptionEngine.VOSK,
        #     TranscriptionEngine.GOOGLE_WEB_SPEECH,
        # ])
        # self.preferred_engines = [
        #     TranscriptionEngine.VOSK,  # Offline, good balance
        #     TranscriptionEngine.WHISPER,  # High accuracy
        #     TranscriptionEngine.GOOGLE_WEB_SPEECH,  # Fallback
        # ]
        self.max_audio_length = 300  # 5 minutes
        self.sample_rate = 16000

# classes (TranscriptionEngine, TranscriptionResult, TranscriptionEngineInterface) 
# are imported from transcription_base.py

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
            TranscriptionEngine.ASSEMBLYAI: AssemblyAIEngine(),
            TranscriptionEngine.GOOGLE_WEB_SPEECH: GoogleWebSpeechEngine(),
            TranscriptionEngine.VOSK: VoskEngine(),
            TranscriptionEngine.WHISPER: WhisperEngine(),
            TranscriptionEngine.SPHINX: SphinxEngine(),
        }
        # ✅ Add AssemblyAI engine
        # self.engines[TranscriptionEngine("assemblyai")] = AssemblyAIEngine()
    
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
                            "words": result.words,
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
# now = datetime.today()
# month_str = now.strftime("%B")
# year_last_two_digits = now.year % 100
# worksheet_name = f"{month_str}{year_last_two_digits}"
# sheet = client.open("Monthly Attendance Sheet").worksheet(worksheet_name)
# print(f"Using worksheet: {worksheet_name}")
# today = datetime.today().strftime("%-m/%-d/%Y")

# --- Settings ---
employee_names = ["Abdullah Al Mamun", "Md. Nazmul Hasan", "Md. Majharul Anwar"]
tz = pytz.timezone("Asia/Dhaka")

# --- Refactored Function for Updating Attendance ---
def _normalize_date_str(date_str: str) -> str:
    """Normalize date like '2/2/2026' to '02/02/2026' for %m/%d/%Y parsing."""
    parts = date_str.strip().split("/")
    if len(parts) != 3:
        return date_str
    try:
        m, d, y = int(parts[0]), int(parts[1]), int(parts[2])
        return f"{m:02d}/{d:02d}/{y:04d}"
    except (ValueError, TypeError):
        return date_str


def update_attendance(employee: str, date_str: str, column_name: str, time_str: str) -> bool:
    """
    Update attendance record with comprehensive error handling.
    
    Returns:
        bool: True if update was successful, False otherwise
    """
    try:
        # Parse the incoming date string (e.g., "1/5/2026")
        # Handle formats like "1/5/2026" or "01/05/2026"
        date_obj = datetime.strptime(date_str, "%m/%d/%Y")  # or "%-m/%-d/%Y" if no leading zeros
    except ValueError:
        # Try alternative format if needed
        try:
            date_obj = datetime.strptime(date_str, "%-m/%-d/%Y")
        except ValueError:
            print(f"Error: Unable to parse date string: {date_str}")
            return False

    month_str = date_obj.strftime("%B")  # e.g., "January"
    year_last_two = date_obj.year % 100  # e.g., 26
    worksheet_name = f"{month_str}{year_last_two}"

    try:
        sheet = client.open("Monthly Attendance Sheet").worksheet(worksheet_name)
        print(f"Using worksheet: {worksheet_name} for date {date_str}")
    except Exception as e:
        print(f"Error: Cannot open worksheet '{worksheet_name}': {e}")
        return False
    try:
        # Debug info
        print(f"Debug: Starting update_attendance for employee={employee}, date={date_str}, column={column_name}, time={time_str}")
        
        # Validate inputs
        if not all([employee, date_str, column_name, time_str]):
            print(f"Error: Missing required parameters. employee={employee}, date={date_str}, column={column_name}, time={time_str}")
            return False
            
        # Get all rows from sheet
        try:
            all_rows = sheet.get_all_values()
            print(f"Debug: Retrieved {len(all_rows)} rows from sheet")
        except Exception as e:
            print(f"Error: Failed to get sheet data: {str(e)}")
            return False
        
        # Check if we have enough rows for headers
        if len(all_rows) < 7:
            print(f"Error: Not enough rows in sheet. Expected at least 7 rows, got {len(all_rows)}")
            return False
            
        # Get headers
        try:
            headers = [str(h).strip() for h in all_rows[6]]
            headers_lower = [h.lower() for h in headers]
            print(f"Debug: Headers found: {headers}")
            
            # Find required columns with better error messages
            required_columns = {
                "name": "name",
                "date": "date",
                "check-in": "check-in",
                "check-out": "check-out",
                "hours logged": "hours logged",
                "over time(h.m)": "over time(h.m)",
                "attendance status": "attendance status"
            }
            
            column_indices = {}
            missing_columns = []
            
            for col_key, col_name in required_columns.items():
                try:
                    column_indices[col_key] = headers_lower.index(col_name.lower()) + 1
                    print(f"Debug: Column '{col_name}' found at index {column_indices[col_key]}")
                except ValueError:
                    missing_columns.append(col_name)
            
            if missing_columns:
                print(f"Error: Missing required columns: {missing_columns}")
                print(f"Debug: Available columns: {headers}")
                return False
                
            # Unpack column indices for readability
            name_col = column_indices["name"]
            date_col = column_indices["date"]
            checkin_col = column_indices["check-in"]
            checkout_col = column_indices["check-out"]
            hours_logged_col = column_indices["hours logged"]
            over_time_col = column_indices["over time(h.m)"]
            attendance_status_col = column_indices["attendance status"]
            
            # Find target column (the column to update)
            try:
                target_col = headers_lower.index(column_name.lower()) + 1
                print(f"Debug: Target column '{column_name}' found at index {target_col}")
            except ValueError:
                print(f"Error: Column '{column_name}' not found in headers")
                print(f"Debug: Available columns: {headers}")
                return False
                
        except Exception as e:
            print(f"Error: Failed to process headers: {str(e)}")
            return False
        
        # Validate date format (assuming date_str is in a specific format)
        try:
            # You might want to parse the date here if needed
            # For now, just check it's not empty
            if not date_str.strip():
                print("Error: Empty date string")
                return False
        except Exception as e:
            print(f"Error: Invalid date format: {str(e)}")
            return False
        
        # Search for employee and date
        last_date = None
        date_found = False
        empty_employee_row_idx = None
        
        print(f"Debug: Starting search from row 8 to {len(all_rows)}")
        
        for idx, row in enumerate(all_rows[7:], start=8):
            try:
                # Debug current row
                if idx <= 15:  # Only print first few rows for debugging
                    print(f"Debug Row {idx}: name='{row[name_col-1]}', date='{row[date_col-1]}'")
                
                row_name = (row[name_col - 1] if len(row) >= name_col else "").strip()
                row_date_str = (row[date_col - 1] if len(row) >= date_col else "").strip()
                
                # If no date in current row, use last known date
                if not row_date_str and last_date is not None:
                    row_date_str = last_date
                    
                if row_date_str:
                    last_date = row_date_str
                
                # Check for empty employee row for the target date
                if row_date_str == date_str and not row_name:
                    empty_employee_row_idx = idx
                    print(f"Debug: Found empty employee row at index {idx} for date {date_str}")
                    continue
                    
                # Check if this row matches both employee and date
                if last_date == date_str and row_name == employee:
                    print(f"Debug: Found matching row at index {idx}")
                    
                    # Update the target cell
                    try:
                        sheet.update_cell(idx, target_col, time_str)
                        print(f"Debug: Updated cell ({idx}, {target_col}) with '{time_str}'")
                        date_found = True
                        
                        # If this is a check-out, calculate hours
                        if column_name.lower() == "check-out":
                            checkin_time_str = (row[checkin_col - 1] if len(row) >= checkin_col else "").strip()
                            
                            if checkin_time_str:
                                try:
                                    # Handle time formats with and without seconds
                                    try:
                                        checkin_time = datetime.strptime(checkin_time_str, "%I:%M:%S %p")
                                    except ValueError:
                                        checkin_time = datetime.strptime(checkin_time_str, "%I:%M %p")
                                    
                                    checkout_time = datetime.strptime(time_str, "%I:%M %p")
                                    hours_logged = (checkout_time - checkin_time).total_seconds() / 3600
                                    over_time = max(0, hours_logged - 8.0)  # Ensure non-negative
                                    
                                    # Update calculated fields
                                    sheet.update_cell(idx, hours_logged_col, f"{hours_logged:.2f}")
                                    sheet.update_cell(idx, over_time_col, f"{over_time:.2f}")
                                    sheet.update_cell(idx, attendance_status_col, "Present")
                                    
                                    print(f"Debug: Calculated hours: logged={hours_logged:.2f}, overtime={over_time:.2f}")
                                    
                                except ValueError as e:
                                    print(f"Error: Failed to parse time for calculation: {str(e)}")
                                    print(f"Debug: checkin_time_str='{checkin_time_str}', time_str='{time_str}'")
                                    return False
                            else:
                                print(f"Error: No check-in time found for employee {employee}")
                                return False
                        
                        print(f"Success: Attendance updated for {employee} on {date_str}")
                        return True
                        
                    except Exception as e:
                        print(f"Error: Failed to update cell: {str(e)}")
                        return False
                        
            except Exception as e:
                print(f"Error: Failed to process row {idx}: {str(e)}")
                continue  # Skip problematic rows and continue searching
        
        # If we found an empty employee row for the date, use it
        if empty_employee_row_idx is not None:
            print(f"Debug: Using empty employee row at index {empty_employee_row_idx}")
            try:
                sheet.update_cell(empty_employee_row_idx, name_col, employee)
                sheet.update_cell(empty_employee_row_idx, target_col, time_str)
                sheet.update_cell(empty_employee_row_idx, hours_logged_col, "0.00")
                sheet.update_cell(empty_employee_row_idx, over_time_col, "0.00")
                sheet.update_cell(empty_employee_row_idx, attendance_status_col, "Present")
                
                print(f"Success: Created new entry in empty row for {employee} on {date_str}")
                return True
                
            except Exception as e:
                print(f"Error: Failed to update empty row: {str(e)}")
                return False
        
        # If no row found, insert a new row
        if not date_found:
            print(f"Debug: No existing row found. Inserting new row.")
            try:
                insert_row_idx = (idx + 1) if 'idx' in locals() and idx > 7 else 8
                
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
                print(f"Success: Inserted new row for {employee} on {date_str} at row {insert_row_idx}")
                return True
                
            except Exception as e:
                print(f"Error: Failed to insert new row: {str(e)}")
                return False
        
        print(f"Debug: No action taken - date_found={date_found}, empty_employee_row_idx={empty_employee_row_idx}")
        return False
        
    except Exception as e:
        print(f"Critical Error: Unexpected error in update_attendance: {str(e)}")
        import traceback
        traceback.print_exc()  # Print full traceback for debugging
        return False
def convert_to_wav(input_path: str, output_path: str = None) -> str:
    """
    Convert any audio (e.g., .ogg, .m4a, .webm, .mp3) to a valid 16-bit PCM mono WAV.
    """
    if output_path is None:
        output_path = tempfile.mktemp(suffix='.wav')

    # Load any audio format supported by ffmpeg
    audio = AudioSegment.from_file(input_path)

    # Ensure mono channel and 16kHz sample rate
    audio = audio.set_channels(1).set_frame_rate(16000)

    # Force export as 16-bit PCM (Vosk compatible)
    audio.export(output_path, format="wav", parameters=["-acodec", "pcm_s16le"])
    return output_path
# --- Helper Functions ---
# def convert_to_wav(input_path: str, output_path: str = None) -> str:
#     """Convert any audio format to WAV for speech recognition"""
#     if output_path is None:
#         output_path = tempfile.mktemp(suffix='.wav')
    
#     audio = AudioSegment.from_file(input_path)
#     audio = audio.set_frame_rate(16000).set_channels(1)
#     audio.export(output_path, format="wav")
#     return output_path

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
