from enum import Enum
from abc import ABC, abstractmethod

class TranscriptionEngine(Enum):
    GOOGLE_WEB_SPEECH = "google_web_speech"
    VOSK = "vosk"
    WHISPER = "whisper"
    SPHINX = "sphinx"
    ASSEMBLYAI = "assemblyai"

class TranscriptionResult:
    """Standardized result format"""
    def __init__(self, text: str, engine: TranscriptionEngine, confidence: float = 1.0, success: bool = True, words: list = None):
        self.text = text
        self.engine = engine
        self.confidence = confidence
        self.success = success
        self.words = words or []

class TranscriptionEngineInterface(ABC):
    """Interface for transcription engines"""
    
    @abstractmethod
    def transcribe(self, audio_path: str) -> TranscriptionResult:
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        pass
