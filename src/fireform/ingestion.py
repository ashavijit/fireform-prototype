from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)
AUDIO_EXTENSIONS = {'.wav', '.mp3', '.m4a', '.ogg', '.flac', '.webm'}

class IncidentInput:

    def __init__(self, whisper_model: str='base') -> None:
        self._whisper_model_name = whisper_model
        self._whisper = None

    def ingest(self, source: str | Path) -> str:
        path = Path(source) if isinstance(source, str) and Path(source).exists() else source if isinstance(source, Path) else None
        if path is not None:
            if path.suffix.lower() in AUDIO_EXTENSIONS:
                return self.from_audio(path)
            if path.suffix.lower() in {'.txt', '.md'}:
                return self.from_text_file(path)
        return self.from_text(str(source))

    def from_text(self, text: str) -> str:
        cleaned = text.strip()
        if not cleaned:
            raise ValueError('Incident description cannot be empty.')
        logger.debug('Ingested %d-character text input.', len(cleaned))
        return cleaned

    def from_text_file(self, path: str | Path) -> str:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f'Text file not found: {path}')
        return self.from_text(path.read_text(encoding='utf-8'))

    def from_audio(self, audio_path: str | Path) -> str:
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f'Audio file not found: {audio_path}')
        logger.info('Transcribing audio file: %s (model=%s)', audio_path.name, self._whisper_model_name)
        model = self._load_whisper()
        result = model.transcribe(str(audio_path))
        transcript = result['text'].strip()
        logger.info('Transcription complete (%d chars).', len(transcript))
        return transcript

    def _load_whisper(self):
        if self._whisper is None:
            try:
                import whisper
            except ImportError as e:
                raise ImportError('Whisper is required for audio transcription. Install it with: pip install openai-whisper') from e
            logger.info("Loading Whisper model '%s'...", self._whisper_model_name)
            self._whisper = whisper.load_model(self._whisper_model_name)
        return self._whisper