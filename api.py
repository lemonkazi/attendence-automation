import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os
import pytz
import tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS
import speech_recognition as sr
from pydub import AudioSegment

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# --- Google Sheets Auth ---
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]
script_dir = os.path.dirname(os.path.abspath(__file__))
credential_path = os.path.join(script_dir, 'credential.json')
creds = ServiceAccountCredentials.from_json_keyfile_name(credential_path, scope)
client = gspread.authorize(creds)

# Get today's date
now = datetime.today()
month_str = now.strftime("%B")  # Get full month name (e.g., August)
year_last_two_digits = now.year % 100  # Get last two digits of the year (e.g., 25)

worksheet_name = f"{month_str}{year_last_two_digits}"
sheet = client.open("Monthly Attendance Sheet").worksheet(worksheet_name)

today = datetime.today().strftime("%-m/%-d/%Y")  # e.g. 8/23/2025

# --- Settings ---
employee_names = ["Abdullah Al Mamun", "Md. Nazmul Hasan", "Md. Majharul Anwar"]
tz = pytz.timezone("Asia/Dhaka")

# --- Refactored Function for Updating Attendance ---
def update_attendance(employee: str, date_str: str, column_name: str, time_str: str) -> bool:
    """
    Updates the specified column (e.g., 'check-in' or 'check-out') for the given employee and date in the Google Sheet.

    Args:
        employee (str): The employee's name.
        date_str (str): The date in format like '8/23/2025'.
        column_name (str): The column header to update (e.g., 'check-in').
        time_str (str): The time string to write.

    Returns:
        bool: True if updated successfully, False otherwise.
    """
    # Read all rows once
    all_rows = sheet.get_all_values()  # includes headers
    headers = [h.strip() for h in all_rows[6]]  # headers in row 7 (index 6)

    # Convert headers to lower case for case-insensitive matching
    headers_lower = [h.lower() for h in headers]

    # Find column indices (1-based for sheet.update_cell)
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
    for idx, row in enumerate(all_rows[7:], start=8):  # data starts from row 8
        row_name = (row[name_col - 1] or "").strip()
        row_date_str = (row[date_col - 1] or "").strip()
        
        # If date is empty, use the last visible date (merged cell)
        if not row_date_str and last_date is not None:
            row_date_str = last_date
            
        if row_date_str:
            last_date = row_date_str
        # If date matches and employee column is empty, mark this row for update
        if row_date_str == date_str and not row_name:
            empty_employee_row_idx = idx
            continue

        if last_date == date_str and row_name == employee:
            sheet.update_cell(idx, target_col, time_str)
            date_found = True
            # If updating 'check-out', calculate and update other columns
            if column_name.lower() == "check-out":
                checkin_time_str = row[checkin_col - 1]
                if checkin_time_str:
                    try:
                        # Parse time strings and calculate time difference
                        checkin_time = datetime.strptime(checkin_time_str, "%I:%M:%S %p")
                        checkout_time = datetime.strptime(time_str, "%I:%M %p")
                        hours_logged = (checkout_time - checkin_time).total_seconds() / 3600
                        over_time = hours_logged - 8.0

                        # Update 'Hours Logged', 'Over Time', and 'Attendance Status' columns
                        sheet.update_cell(idx, hours_logged_col, f"{hours_logged:.2f}")
                        sheet.update_cell(idx, over_time_col, f"{over_time:.2f}")
                        sheet.update_cell(idx, attendance_status_col, "Present")
                    except ValueError:
                        return False
                else:
                    return False  # No check-in time found, cannot calculate hours logged

            return True
        if row_date_str:  # Track the last row with a date
            last_date_row_idx = idx
    
    # If date found but employee column was empty, update that row
    if empty_employee_row_idx is not None:
        sheet.update_cell(empty_employee_row_idx, name_col, employee)
        sheet.update_cell(empty_employee_row_idx, target_col, time_str)
        sheet.update_cell(empty_employee_row_idx, hours_logged_col, "0.00")
        sheet.update_cell(empty_employee_row_idx, over_time_col, "0.00")
        sheet.update_cell(empty_employee_row_idx, attendance_status_col, "Present")
        return True
    # If date not found, insert a new row right after the last row with a date
    if not date_found:
        insert_row_idx = last_date_row_idx + 1 if last_date_row_idx is not None else 8
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

# --- Audio Transcription Functions ---
def convert_to_wav(input_path: str, output_path: str = None) -> str:
    """Convert any audio format to WAV for speech recognition"""
    if output_path is None:
        output_path = tempfile.mktemp(suffix='.wav')
    audio = AudioSegment.from_file(input_path)
    audio = audio.set_frame_rate(16000).set_channels(1)
    audio.export(output_path, format="wav")
    return output_path

# --- Routes ---
@app.route('/attendance', methods=['POST'])
def handle_attendance():
    """Handle attendance check-in/check-out requests"""
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
    """
    Transcribe audio file to text - supports multiple formats with FFmpeg
    """
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Empty filename'}), 400

        allowed_extensions = ['.mp3', '.wav', '.webm', '.ogg', '.m4a', '.mp4', '.flac', '.mpeg']
        file_extension = os.path.splitext(file.filename.lower())[1]
        if file_extension not in allowed_extensions:
            return jsonify({'error': f"Unsupported file type. Supported formats: MP3, WAV, WebM, OGG, M4A, MP4, FLAC"}), 400

        # Create temporary input file
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as input_temp_file:
            file.save(input_temp_file.name)
            input_path = input_temp_file.name

        wav_path = None
        try:
            wav_path = convert_to_wav(input_path)
            recognizer = sr.Recognizer()

            with sr.AudioFile(wav_path) as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio_data = recognizer.record(source)

                try:
                    text = recognizer.recognize_google(audio_data)
                    engine = "google_web_speech"
                    success = True
                    message = "Transcription completed successfully"
                except sr.UnknownValueError:
                    text = ""
                    engine = "google_web_speech"
                    success = True
                    message = "Audio was clear but no speech could be understood"
                except sr.RequestError:
                    try:
                        text = recognizer.recognize_sphinx(audio_data)
                        engine = "sphinx_offline"
                        success = True
                        message = "Transcription completed using offline engine"
                    except sr.UnknownValueError:
                        text = ""
                        engine = "sphinx_offline"
                        success = True
                        message = "Offline engine could not understand audio"
                    except Exception as sphinx_error:
                        return jsonify({'error': f"All transcription engines failed: {str(sphinx_error)}"}), 500

            return jsonify({
                "success": success,
                "text": text,
                "engine": engine,
                "file_name": file.filename,
                "message": message,
            })

        finally:
            if os.path.exists(input_path):
                os.unlink(input_path)
            if wav_path and os.path.exists(wav_path):
                os.unlink(wav_path)

    except Exception as e:
        return jsonify({'error': f"Transcription failed: {str(e)}"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "services": {
            "attendance": "active",
            "transcription": "active"
        },
        "supported_formats": ["MP3", "WAV", "WebM", "OGG", "M4A", "MP4", "FLAC"],
        "engines": ["google_web_speech", "sphinx_offline"],
        "note": "FFmpeg required for non-WAV formats"
    })

@app.route('/', methods=['GET'])
def index():
    """Root endpoint with service information"""
    return jsonify({
        "message": "Attendance and Transcription Service",
        "endpoints": {
            "/attendance": "POST - Submit attendance check-in/check-out",
            "/transcribe": "POST - Transcribe audio files",
            "/health": "GET - Service health check"
        }
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8502, debug=True)