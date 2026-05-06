import requests
import time
import os
import logging
from typing import Dict, Any
#  for production
# from .transcription_base import TranscriptionEngineInterface, TranscriptionResult, TranscriptionEngine
from transcription_base import TranscriptionEngineInterface, TranscriptionResult, TranscriptionEngine

logger = logging.getLogger(__name__)

class AssemblyAIEngine(TranscriptionEngineInterface):
    def __init__(self):
        self.api_key = os.getenv("ASSEMBLYAI_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("Missing ASSEMBLYAI_API_KEY environment variable")
        
        self.base_url = "https://api.assemblyai.com/v2"
        self.headers = {"authorization": self.api_key}

    def is_available(self) -> bool:
        return bool(self.api_key and self.api_key != "YOUR_ASSEMBLYAI_KEY")

    def _upload_audio(self, file_path: str) -> str:
        """Uploads local audio file to AssemblyAI."""
        with open(file_path, "rb") as f:
            response = requests.post(f"{self.base_url}/upload", headers=self.headers, data=f)
        response.raise_for_status()
        return response.json()["upload_url"]

    def transcribe(self, audio_path: str) -> TranscriptionResult:
        """Transcribe the given audio using AssemblyAI."""
        if not self.is_available():
            raise RuntimeError("AssemblyAI API key missing or invalid.")

        try:
            logger.info("Uploading file to AssemblyAI...")
            audio_url = self._upload_audio(audio_path)
            # u3-rt-pro
            data = {
                "audio_url": audio_url, 
                "language_detection": True,
                "format_text":True,
                "punctuate":True,
                "domain": "medical-v1", 
                "temperature": 0,
                "speech_models": ["universal-2"]
            }
            response = requests.post(f"{self.base_url}/transcript", json=data, headers=self.headers)
            response.raise_for_status()
            transcript_id = response.json()["id"]

            polling_endpoint = f"{self.base_url}/transcript/{transcript_id}"

            logger.info("Polling AssemblyAI for transcription...")
            while True:
                poll_res = requests.get(polling_endpoint, headers=self.headers).json()
                if poll_res["status"] == "completed":
                    text = poll_res["text"]
                    words = poll_res.get("words", [])
                    return TranscriptionResult(
                        text=text,
                        engine=TranscriptionEngine("assemblyai"),
                        confidence=1.0,
                        words=words
                    )
                elif poll_res["status"] == "error":
                    raise RuntimeError(f"AssemblyAI failed: {poll_res['error']}")
                time.sleep(3)

        except Exception as e:
            logger.error(f"AssemblyAI transcription error: {e}")
            raise
