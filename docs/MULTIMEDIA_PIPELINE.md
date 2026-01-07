# CHIMERA Multimedia Extraction Pipeline

## Overview

Full multimedia support for cognitive archaeology:
- **Images**: EXIF, GPS, AI vision analysis, object detection
- **Audio**: Register on first pass, transcribe on demand
- **Video**: Frame extraction, scene detection (future)

## Image Processing Pipeline

### Phase 1: Parallel Extraction (USB Excavator)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     IMAGE DISCOVERY & EXTRACTION                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  [image.jpg] ─────────────────┬─────────────────┬─────────────────┐    │
│                               │                 │                 │    │
│                               ▼                 ▼                 ▼    │
│                         ┌──────────┐    ┌────────────┐    ┌─────────┐ │
│                         │   EXIF   │    │    GPS     │    │ Thumbnail│ │
│                         │ Extract  │    │  Geocode   │    │ Generate │ │
│                         └────┬─────┘    └─────┬──────┘    └────┬────┘ │
│                              │                │                 │      │
│                              ▼                ▼                 ▼      │
│                         ┌──────────────────────────────────────────┐  │
│                         │              LOCAL STORAGE                │  │
│                         │  chunks/img_{hash}.json                  │  │
│                         │  entities/img_{hash}.json                │  │
│                         │  thumbnails/img_{hash}_thumb.webp        │  │
│                         └──────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Phase 2: Server-Side AI Analysis (On Sync)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      AI VISION ANALYSIS (GPU)                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  [Synced Image] ─────────┬─────────────┬─────────────┬──────────────┐  │
│                          │             │             │              │  │
│                          ▼             ▼             ▼              ▼  │
│                    ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌─────────┐│
│                    │  OpenAI  │ │  Claude   │ │  Local   │ │  OCR    ││
│                    │  Vision  │ │  Vision   │ │  BLIP-2  │ │Tesseract││
│                    └────┬─────┘ └─────┬─────┘ └────┬─────┘ └────┬────┘│
│                         │             │            │             │     │
│                         └─────────────┴────────────┴─────────────┘     │
│                                       │                                 │
│                                       ▼                                 │
│                         ┌──────────────────────────────────────────┐   │
│                         │           UNIFIED ANALYSIS                │   │
│                         │  - Description (natural language)         │   │
│                         │  - Category (Nature, People, Urban...)   │   │
│                         │  - Detected objects                       │   │
│                         │  - Extracted text (OCR)                   │   │
│                         │  - Technical quality score                │   │
│                         │  - Content analysis                       │   │
│                         └──────────────────────────────────────────┘   │
│                                       │                                 │
│                                       ▼                                 │
│                         ┌──────────────────────────────────────────┐   │
│                         │        VECTOR EMBEDDINGS                  │   │
│                         │  - CLIP embeddings (visual)               │   │
│                         │  - Text embeddings (description)          │   │
│                         │  - Combined multimodal                    │   │
│                         └──────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Audio Processing Pipeline

### Phase 1: Register Only (USB Excavator)

```python
# Fast pass - just register metadata, no transcription
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".wma"}

async def process_audio_fast(file_path: Path) -> dict:
    """Register audio file without transcription."""
    return {
        "file_id": generate_id(file_path),
        "file_path": str(file_path),
        "file_type": "audio",
        "extension": file_path.suffix,
        "file_size": file_path.stat().st_size,
        "duration": get_audio_duration(file_path),  # Quick metadata read
        "needs_transcription": True,
        "transcription_status": "pending",
    }
```

### Phase 2: On-Demand Transcription (Server)

```python
# User requests transcription via CLI or API
async def transcribe_audio(file_id: str, provider: str = "whisper") -> dict:
    """Transcribe audio on demand."""
    
    providers = {
        "whisper": WhisperTranscriber(),      # Local (free)
        "whisper-api": OpenAIWhisper(),       # OpenAI API
        "deepgram": DeepgramTranscriber(),    # Fast, accurate
        "assemblyai": AssemblyAITranscriber(), # Speaker diarization
    }
    
    transcriber = providers[provider]
    result = await transcriber.transcribe(file_path)
    
    return {
        "transcript": result.text,
        "segments": result.segments,  # Timestamped
        "speakers": result.speakers,   # If diarization
        "language": result.language,
        "confidence": result.confidence,
    }
```

## Data Structures

### Image Entity Record

```json
{
  "id": "img_abc123",
  "file_path": "/mnt/e/Photos/vacation_2024/beach.jpg",
  "file_type": "image",
  "mime_type": "image/jpeg",
  "file_size": 4523678,
  
  "exif": {
    "camera": {
      "make": "Apple",
      "model": "iPhone 14 Pro",
      "lens": "iPhone 14 Pro back triple camera"
    },
    "settings": {
      "iso": 64,
      "aperture": "f/1.78",
      "shutter_speed": "1/1000",
      "focal_length": "6.86mm"
    },
    "timestamps": {
      "date_taken": "2024-07-15T14:32:00",
      "date_modified": "2024-07-15T14:32:00"
    }
  },
  
  "gps": {
    "latitude": 21.2868,
    "longitude": -157.8442,
    "altitude": 5.2,
    "location_name": "Waikiki Beach, Honolulu, HI",
    "country": "United States",
    "geocoded": true
  },
  
  "ai_analysis": {
    "provider": "openai",
    "model": "gpt-4-vision",
    "description": "A beautiful sunset over Waikiki Beach with golden light reflecting on the ocean waves. Palm trees silhouetted against an orange and pink sky.",
    "category": "Nature",
    "confidence": 0.94,
    "detected_objects": ["beach", "ocean", "sunset", "palm trees", "waves", "sky"],
    "extracted_text": "",
    "content_analysis": {
      "people_count": 0,
      "indoor_outdoor": "outdoor",
      "time_of_day": "sunset",
      "weather": "clear",
      "mood": "serene"
    },
    "technical_analysis": {
      "quality_score": 0.91,
      "composition_score": 0.88,
      "lighting": "golden hour",
      "colors": ["orange", "pink", "blue", "gold"]
    }
  },
  
  "thumbnails": {
    "small": "thumbnails/img_abc123_150.webp",
    "medium": "thumbnails/img_abc123_400.webp",
    "large": "thumbnails/img_abc123_800.webp"
  },
  
  "embeddings": {
    "visual": [0.123, 0.456, ...],  // CLIP embedding
    "text": [0.789, 0.012, ...],    // Description embedding
    "combined": [0.345, 0.678, ...] // Multimodal
  }
}
```

### Audio Entity Record

```json
{
  "id": "aud_xyz789",
  "file_path": "/mnt/e/Recordings/meeting_2024-01-15.m4a",
  "file_type": "audio",
  "mime_type": "audio/mp4",
  "file_size": 15234567,
  
  "metadata": {
    "duration_seconds": 3600,
    "duration_formatted": "1:00:00",
    "sample_rate": 44100,
    "channels": 2,
    "bitrate": 128000
  },
  
  "transcription": {
    "status": "completed",  // or "pending", "processing", "failed"
    "provider": "whisper",
    "model": "whisper-large-v3",
    "language": "en",
    "confidence": 0.92,
    "text": "Welcome everyone to the quarterly review meeting...",
    "segments": [
      {
        "start": 0.0,
        "end": 5.2,
        "text": "Welcome everyone to the quarterly review meeting.",
        "speaker": "Speaker 1",
        "confidence": 0.95
      }
    ],
    "speakers": [
      {"id": "Speaker 1", "speaking_time": 1200},
      {"id": "Speaker 2", "speaking_time": 800}
    ]
  },
  
  "entities_extracted": [
    {"type": "PERSON", "value": "John Smith", "count": 5},
    {"type": "ORG", "value": "Nexless Healthcare", "count": 3},
    {"type": "DATE", "value": "Q1 2024", "count": 2}
  ]
}
```

## Implementation Files

### src/chimera/extractors/image.py

```python
"""Image extraction with parallel processing."""

import asyncio
from pathlib import Path
from typing import Optional, Dict, Any
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import hashlib

class ImageExtractor:
    """Extract metadata, EXIF, GPS from images."""
    
    SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"}
    
    def __init__(self):
        self.geocoder = None  # Lazy load
    
    async def extract(self, file_path: Path) -> Dict[str, Any]:
        """Extract all image data in parallel."""
        
        # Run all extractions concurrently
        exif_task = asyncio.create_task(self._extract_exif(file_path))
        thumb_task = asyncio.create_task(self._generate_thumbnail(file_path))
        hash_task = asyncio.create_task(self._compute_hash(file_path))
        
        exif_data, thumbnail_path, file_hash = await asyncio.gather(
            exif_task, thumb_task, hash_task
        )
        
        # Extract GPS and geocode if available
        gps_data = await self._extract_gps(exif_data)
        
        return {
            "id": f"img_{file_hash[:12]}",
            "file_path": str(file_path),
            "file_type": "image",
            "extension": file_path.suffix.lower(),
            "file_hash": file_hash,
            "exif": exif_data,
            "gps": gps_data,
            "thumbnail": thumbnail_path,
            "needs_ai_analysis": True,
        }
    
    async def _extract_exif(self, file_path: Path) -> Dict[str, Any]:
        """Extract EXIF metadata."""
        try:
            with Image.open(file_path) as img:
                exif = img._getexif()
                if not exif:
                    return {}
                
                exif_data = {}
                for tag_id, value in exif.items():
                    tag = TAGS.get(tag_id, tag_id)
                    if isinstance(value, bytes):
                        continue  # Skip binary data
                    exif_data[tag] = value
                
                return self._organize_exif(exif_data)
        except Exception:
            return {}
    
    async def _extract_gps(self, exif_data: Dict) -> Optional[Dict]:
        """Extract and geocode GPS coordinates."""
        gps_info = exif_data.get("GPSInfo", {})
        if not gps_info:
            return None
        
        try:
            lat = self._convert_gps_coord(gps_info.get("GPSLatitude"), 
                                           gps_info.get("GPSLatitudeRef"))
            lon = self._convert_gps_coord(gps_info.get("GPSLongitude"),
                                           gps_info.get("GPSLongitudeRef"))
            
            if lat is None or lon is None:
                return None
            
            # Geocode to location name
            location_name = await self._geocode(lat, lon)
            
            return {
                "latitude": lat,
                "longitude": lon,
                "altitude": gps_info.get("GPSAltitude"),
                "location_name": location_name,
            }
        except Exception:
            return None
    
    async def _geocode(self, lat: float, lon: float) -> str:
        """Reverse geocode coordinates to location name."""
        try:
            from geopy.geocoders import Nominatim
            if self.geocoder is None:
                self.geocoder = Nominatim(user_agent="chimera")
            
            location = self.geocoder.reverse(f"{lat}, {lon}")
            if location:
                return location.address
        except Exception:
            pass
        return f"{lat:.4f}, {lon:.4f}"
    
    async def _generate_thumbnail(self, file_path: Path) -> Optional[str]:
        """Generate WebP thumbnail."""
        try:
            thumb_dir = file_path.parent / "thumbnails"
            thumb_dir.mkdir(exist_ok=True)
            
            thumb_path = thumb_dir / f"{file_path.stem}_thumb.webp"
            
            with Image.open(file_path) as img:
                img.thumbnail((400, 400))
                img.save(thumb_path, "WEBP", quality=80)
            
            return str(thumb_path)
        except Exception:
            return None
    
    async def _compute_hash(self, file_path: Path) -> str:
        """Compute file hash for deduplication."""
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    def _organize_exif(self, raw_exif: Dict) -> Dict:
        """Organize EXIF into structured categories."""
        return {
            "camera": {
                "make": raw_exif.get("Make"),
                "model": raw_exif.get("Model"),
                "lens": raw_exif.get("LensModel"),
            },
            "settings": {
                "iso": raw_exif.get("ISOSpeedRatings"),
                "aperture": raw_exif.get("FNumber"),
                "shutter_speed": raw_exif.get("ExposureTime"),
                "focal_length": raw_exif.get("FocalLength"),
            },
            "timestamps": {
                "date_taken": raw_exif.get("DateTimeOriginal"),
                "date_modified": raw_exif.get("DateTime"),
            },
        }
    
    def _convert_gps_coord(self, coord, ref) -> Optional[float]:
        """Convert GPS coordinate to decimal degrees."""
        if not coord or not ref:
            return None
        
        degrees, minutes, seconds = coord
        decimal = degrees + minutes / 60 + seconds / 3600
        
        if ref in ("S", "W"):
            decimal = -decimal
        
        return decimal
```

### src/chimera/extractors/audio.py

```python
"""Audio extraction and on-demand transcription."""

from pathlib import Path
from typing import Optional, Dict, Any
import hashlib

class AudioExtractor:
    """Extract audio metadata, transcribe on demand."""
    
    SUPPORTED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".wma"}
    
    async def extract_fast(self, file_path: Path) -> Dict[str, Any]:
        """Fast extraction - metadata only, no transcription."""
        
        file_hash = await self._compute_hash(file_path)
        duration = await self._get_duration(file_path)
        
        return {
            "id": f"aud_{file_hash[:12]}",
            "file_path": str(file_path),
            "file_type": "audio",
            "extension": file_path.suffix.lower(),
            "file_hash": file_hash,
            "file_size": file_path.stat().st_size,
            "duration_seconds": duration,
            "transcription": {
                "status": "pending",
                "text": None,
            },
            "needs_transcription": True,
        }
    
    async def _get_duration(self, file_path: Path) -> Optional[float]:
        """Get audio duration from metadata."""
        try:
            from mutagen import File
            audio = File(file_path)
            if audio and audio.info:
                return audio.info.length
        except Exception:
            pass
        return None
    
    async def _compute_hash(self, file_path: Path) -> str:
        """Compute file hash."""
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()


class AudioTranscriber:
    """On-demand audio transcription."""
    
    def __init__(self, provider: str = "whisper"):
        self.provider = provider
    
    async def transcribe(self, file_path: Path) -> Dict[str, Any]:
        """Transcribe audio file."""
        
        if self.provider == "whisper":
            return await self._transcribe_whisper(file_path)
        elif self.provider == "openai":
            return await self._transcribe_openai(file_path)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")
    
    async def _transcribe_whisper(self, file_path: Path) -> Dict[str, Any]:
        """Local Whisper transcription."""
        try:
            import whisper
            model = whisper.load_model("base")  # or "small", "medium", "large"
            result = model.transcribe(str(file_path))
            
            return {
                "status": "completed",
                "provider": "whisper-local",
                "text": result["text"],
                "segments": result["segments"],
                "language": result["language"],
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e),
            }
    
    async def _transcribe_openai(self, file_path: Path) -> Dict[str, Any]:
        """OpenAI Whisper API transcription."""
        try:
            from openai import OpenAI
            client = OpenAI()
            
            with open(file_path, "rb") as f:
                result = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    response_format="verbose_json",
                )
            
            return {
                "status": "completed",
                "provider": "openai-whisper",
                "text": result.text,
                "segments": result.segments,
                "language": result.language,
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e),
            }
```

### src/chimera/ai/vision.py

```python
"""AI Vision providers for image analysis."""

from pathlib import Path
from typing import Dict, Any
from abc import ABC, abstractmethod
import base64

class VisionProvider(ABC):
    """Base class for vision AI providers."""
    
    @abstractmethod
    async def analyze(self, image_path: Path) -> Dict[str, Any]:
        pass


class OpenAIVision(VisionProvider):
    """OpenAI GPT-4 Vision analysis."""
    
    def __init__(self, api_key: str):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key)
    
    async def analyze(self, image_path: Path) -> Dict[str, Any]:
        # Read and encode image
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode()
        
        response = self.client.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """Analyze this image and provide:
1. A detailed description (2-3 sentences)
2. Category (Nature, People, Urban, Documents, Art, Food, Technology, Other)
3. List of detected objects
4. Any visible text (OCR)
5. Technical assessment (quality, composition, lighting)
6. Content analysis (indoor/outdoor, time of day, mood)

Respond in JSON format."""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=1000
        )
        
        # Parse JSON response
        import json
        try:
            return json.loads(response.choices[0].message.content)
        except:
            return {"description": response.choices[0].message.content}


class ClaudeVision(VisionProvider):
    """Anthropic Claude Vision analysis."""
    
    def __init__(self, api_key: str):
        from anthropic import Anthropic
        self.client = Anthropic(api_key=api_key)
    
    async def analyze(self, image_path: Path) -> Dict[str, Any]:
        import base64
        
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode()
        
        # Determine media type
        suffix = image_path.suffix.lower()
        media_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg", 
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        media_type = media_types.get(suffix, "image/jpeg")
        
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data,
                            }
                        },
                        {
                            "type": "text",
                            "text": """Analyze this image comprehensively. Provide:
1. Description (detailed, 2-3 sentences)
2. Category: Nature/People/Urban/Documents/Art/Food/Technology/Other
3. Detected objects (list)
4. Extracted text if any (OCR)
5. Technical quality assessment
6. Content analysis (setting, mood, time of day)

Return as JSON."""
                        }
                    ]
                }
            ]
        )
        
        import json
        try:
            return json.loads(response.content[0].text)
        except:
            return {"description": response.content[0].text}


class LocalVision(VisionProvider):
    """Local BLIP-2 vision analysis (no API cost)."""
    
    def __init__(self):
        self.model = None
        self.processor = None
    
    def _load_model(self):
        if self.model is None:
            from transformers import Blip2Processor, Blip2ForConditionalGeneration
            import torch
            
            self.processor = Blip2Processor.from_pretrained("Salesforce/blip2-opt-2.7b")
            self.model = Blip2ForConditionalGeneration.from_pretrained(
                "Salesforce/blip2-opt-2.7b",
                torch_dtype=torch.float16,
                device_map="auto"
            )
    
    async def analyze(self, image_path: Path) -> Dict[str, Any]:
        from PIL import Image
        
        self._load_model()
        
        image = Image.open(image_path)
        
        # Generate description
        inputs = self.processor(image, return_tensors="pt").to("cuda", torch.float16)
        generated_ids = self.model.generate(**inputs, max_length=100)
        description = self.processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
        
        return {
            "description": description,
            "provider": "blip2-local",
            "category": "Unknown",  # BLIP doesn't categorize
            "detected_objects": [],
        }
```

## Updated USB Excavator

### src/chimera/usb/excavator.py (additions)

```python
# Add to supported extensions
SUPPORTED_EXTENSIONS = {
    # Documents
    ".txt", ".md", ".pdf", ".docx", ".doc",
    # Code
    ".py", ".js", ".ts", ".java", ".c", ".cpp", ".h",
    # Data
    ".json", ".yaml", ".yml", ".xml", ".csv",
    # Web
    ".html", ".css", ".sql",
    # Images (NEW)
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff",
    # Audio (NEW - register only)
    ".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac",
}

async def process_file(self, file_path: Path) -> Optional[dict]:
    """Process file based on type."""
    
    ext = file_path.suffix.lower()
    
    # Image processing
    if ext in ImageExtractor.SUPPORTED_EXTENSIONS:
        from chimera.extractors.image import ImageExtractor
        extractor = ImageExtractor()
        return await extractor.extract(file_path)
    
    # Audio processing (register only)
    if ext in AudioExtractor.SUPPORTED_EXTENSIONS:
        from chimera.extractors.audio import AudioExtractor
        extractor = AudioExtractor()
        return await extractor.extract_fast(file_path)
    
    # Text/document processing (existing)
    return await self._process_text_file(file_path)
```

## Shell Commands

```python
# Add to shell.py

"/transcribe": self.cmd_transcribe,    # Transcribe audio on demand
"/analyze-image": self.cmd_analyze,    # Run AI vision on image
"/images": self.cmd_images,            # List indexed images
"/audio": self.cmd_audio,              # List indexed audio

async def cmd_transcribe(self, args: str):
    """Transcribe audio file on demand."""
    if not args:
        console.print("[yellow]Usage: /transcribe <file_id or path>[/yellow]")
        return
    
    console.print(f"[yellow]🎤 Transcribing...[/yellow]")
    
    from chimera.extractors.audio import AudioTranscriber
    transcriber = AudioTranscriber(provider="whisper")
    result = await transcriber.transcribe(Path(args))
    
    if result["status"] == "completed":
        console.print(f"[green]✓ Transcription complete[/green]")
        console.print(f"\n{result['text'][:500]}...")
    else:
        console.print(f"[red]✗ Failed: {result.get('error')}[/red]")

async def cmd_analyze(self, args: str):
    """Run AI vision analysis on image."""
    if not args:
        console.print("[yellow]Usage: /analyze-image <file_path> [--provider openai|claude|local][/yellow]")
        return
    
    console.print(f"[yellow]🔍 Analyzing image...[/yellow]")
    
    from chimera.ai.vision import OpenAIVision
    analyzer = OpenAIVision(api_key=os.getenv("OPENAI_API_KEY"))
    result = await analyzer.analyze(Path(args))
    
    console.print(Panel.fit(
        f"[bold]Description:[/bold] {result.get('description')}\n\n"
        f"[bold]Category:[/bold] {result.get('category')}\n"
        f"[bold]Objects:[/bold] {', '.join(result.get('detected_objects', []))}\n"
        f"[bold]Text:[/bold] {result.get('extracted_text', 'None')}",
        border_style="cyan"
    ))
```

## Dependencies

Add to `pyproject.toml`:

```toml
dependencies = [
    # ... existing ...
    
    # Image processing
    "pillow>=10.0.0",
    "geopy>=2.4.0",         # Geocoding
    
    # Audio processing  
    "mutagen>=1.47.0",      # Audio metadata
    "openai-whisper>=20231117",  # Local transcription (optional)
    
    # AI Vision (optional)
    "transformers>=4.35.0",  # BLIP-2
    "torch>=2.0.0",          # PyTorch
]

[project.optional-dependencies]
vision = [
    "openai>=1.0.0",
    "anthropic>=0.18.0",
    "transformers>=4.35.0",
]

audio = [
    "openai-whisper>=20231117",
    "deepgram-sdk>=3.0.0",
]
```

## Summary

| Media Type | USB Excavator | Server Processing | On-Demand |
|------------|---------------|-------------------|-----------|
| **Text/Docs** | Full chunking + entities | Embeddings | - |
| **Images** | EXIF + GPS + thumbnails | AI Vision analysis | - |
| **Audio** | Register + duration only | - | Transcription |
| **Video** | Register only (future) | - | Frame extraction |

This ensures:
1. **Fast USB excavation** - no heavy processing
2. **Rich metadata** - all EXIF/GPS extracted immediately
3. **Deferred AI** - expensive analysis happens on server
4. **On-demand audio** - transcription only when requested
