"""Audio extraction and on-demand transcription.

Phase 1 (USB Excavator): Register only - extract metadata, no transcription
Phase 2 (Server): On-demand transcription via Whisper or API
"""

import asyncio
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

# Supported audio extensions
AUDIO_EXTENSIONS = {
    ".mp3", ".wav", ".m4a", ".flac", ".ogg", 
    ".aac", ".wma", ".opus", ".aiff"
}


class AudioExtractor:
    """Extract audio metadata without transcription."""
    
    SUPPORTED_EXTENSIONS = AUDIO_EXTENSIONS
    
    async def extract_fast(self, file_path: Path) -> Dict[str, Any]:
        """Fast extraction - metadata only, no transcription."""
        
        file_hash = await self._compute_hash(file_path)
        metadata = await self._extract_metadata(file_path)
        
        return {
            "id": f"aud_{file_hash[:12]}",
            "file_path": str(file_path),
            "file_name": file_path.name,
            "file_type": "audio",
            "extension": file_path.suffix.lower(),
            "file_size": file_path.stat().st_size,
            "file_hash": file_hash,
            "metadata": metadata,
            "transcription": {
                "status": "pending",
                "text": None,
                "segments": None,
            },
            "needs_transcription": True,
            "extracted_at": datetime.now().isoformat(),
        }
    
    async def _extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        """Extract audio metadata using mutagen."""
        try:
            from mutagen import File
            from mutagen.mp3 import MP3
            from mutagen.mp4 import MP4
            from mutagen.flac import FLAC
            
            audio = File(file_path)
            
            if audio is None:
                return {"duration_seconds": None}
            
            metadata = {
                "duration_seconds": round(audio.info.length, 2) if audio.info else None,
            }
            
            # Format duration
            if metadata["duration_seconds"]:
                duration = metadata["duration_seconds"]
                hours = int(duration // 3600)
                minutes = int((duration % 3600) // 60)
                seconds = int(duration % 60)
                
                if hours > 0:
                    metadata["duration_formatted"] = f"{hours}:{minutes:02d}:{seconds:02d}"
                else:
                    metadata["duration_formatted"] = f"{minutes}:{seconds:02d}"
            
            # Technical info
            if hasattr(audio.info, 'sample_rate'):
                metadata["sample_rate"] = audio.info.sample_rate
            if hasattr(audio.info, 'channels'):
                metadata["channels"] = audio.info.channels
            if hasattr(audio.info, 'bitrate'):
                metadata["bitrate"] = audio.info.bitrate
            
            # ID3/metadata tags
            tags = {}
            if hasattr(audio, 'tags') and audio.tags:
                # Common tag mappings
                tag_map = {
                    'TIT2': 'title',
                    'TPE1': 'artist',
                    'TALB': 'album',
                    'TDRC': 'year',
                    'TCON': 'genre',
                    '\xa9nam': 'title',  # MP4
                    '\xa9ART': 'artist',  # MP4
                    '\xa9alb': 'album',   # MP4
                }
                
                for tag_key, tag_name in tag_map.items():
                    if tag_key in audio.tags:
                        value = audio.tags[tag_key]
                        if hasattr(value, 'text'):
                            tags[tag_name] = str(value.text[0]) if value.text else None
                        elif isinstance(value, list):
                            tags[tag_name] = str(value[0]) if value else None
                        else:
                            tags[tag_name] = str(value)
            
            if tags:
                metadata["tags"] = tags
            
            return metadata
            
        except ImportError:
            logger.debug("mutagen not available for audio metadata")
            return {"duration_seconds": None}
        except Exception as e:
            logger.debug(f"Audio metadata extraction failed: {e}")
            return {"duration_seconds": None}
    
    async def _compute_hash(self, file_path: Path) -> str:
        """Compute file hash."""
        hasher = hashlib.md5()
        
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        
        return hasher.hexdigest()


class TranscriptionProvider(ABC):
    """Base class for transcription providers."""
    
    @abstractmethod
    async def transcribe(self, file_path: Path) -> Dict[str, Any]:
        pass


class WhisperLocalTranscriber(TranscriptionProvider):
    """Local Whisper transcription (free, requires GPU)."""
    
    def __init__(self, model_size: str = "base"):
        self.model_size = model_size
        self._model = None
    
    def _load_model(self):
        if self._model is None:
            import whisper
            self._model = whisper.load_model(self.model_size)
    
    async def transcribe(self, file_path: Path) -> Dict[str, Any]:
        try:
            # Run in executor to not block
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._transcribe_sync,
                file_path
            )
            return result
        except Exception as e:
            return {
                "status": "failed",
                "provider": "whisper-local",
                "error": str(e),
            }
    
    def _transcribe_sync(self, file_path: Path) -> Dict[str, Any]:
        import whisper
        
        self._load_model()
        result = self._model.transcribe(str(file_path))
        
        # Format segments
        segments = []
        for seg in result.get("segments", []):
            segments.append({
                "start": round(seg["start"], 2),
                "end": round(seg["end"], 2),
                "text": seg["text"].strip(),
            })
        
        return {
            "status": "completed",
            "provider": "whisper-local",
            "model": self.model_size,
            "text": result["text"].strip(),
            "language": result.get("language"),
            "segments": segments,
        }


class OpenAIWhisperTranscriber(TranscriptionProvider):
    """OpenAI Whisper API transcription."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
    
    async def transcribe(self, file_path: Path) -> Dict[str, Any]:
        try:
            from openai import OpenAI
            import os
            
            client = OpenAI(api_key=self.api_key or os.getenv("OPENAI_API_KEY"))
            
            with open(file_path, "rb") as f:
                result = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    response_format="verbose_json",
                )
            
            # Format segments
            segments = []
            if hasattr(result, 'segments') and result.segments:
                for seg in result.segments:
                    segments.append({
                        "start": seg.get("start", 0),
                        "end": seg.get("end", 0),
                        "text": seg.get("text", "").strip(),
                    })
            
            return {
                "status": "completed",
                "provider": "openai-whisper",
                "model": "whisper-1",
                "text": result.text,
                "language": getattr(result, 'language', None),
                "segments": segments,
            }
            
        except Exception as e:
            return {
                "status": "failed",
                "provider": "openai-whisper",
                "error": str(e),
            }


class AudioTranscriber:
    """Unified transcription interface."""
    
    PROVIDERS = {
        "whisper": WhisperLocalTranscriber,
        "whisper-local": WhisperLocalTranscriber,
        "openai": OpenAIWhisperTranscriber,
        "openai-whisper": OpenAIWhisperTranscriber,
    }
    
    def __init__(self, provider: str = "whisper", **kwargs):
        if provider not in self.PROVIDERS:
            raise ValueError(f"Unknown provider: {provider}. Available: {list(self.PROVIDERS.keys())}")
        
        self.provider_name = provider
        self.provider = self.PROVIDERS[provider](**kwargs)
    
    async def transcribe(self, file_path: Path) -> Dict[str, Any]:
        """Transcribe audio file."""
        return await self.provider.transcribe(file_path)


# Convenience functions
async def extract_audio_fast(file_path: Path) -> Dict[str, Any]:
    """Fast audio extraction (metadata only)."""
    extractor = AudioExtractor()
    return await extractor.extract_fast(file_path)


async def transcribe_audio(
    file_path: Path, 
    provider: str = "whisper",
    **kwargs
) -> Dict[str, Any]:
    """Transcribe audio file."""
    transcriber = AudioTranscriber(provider=provider, **kwargs)
    return await transcriber.transcribe(file_path)
