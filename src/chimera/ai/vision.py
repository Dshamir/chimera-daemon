"""AI Vision providers for image analysis.

Supports:
- OpenAI GPT-4 Vision
- Anthropic Claude Vision
- Local BLIP-2 (no API cost)
"""

import base64
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class VisionProvider(ABC):
    """Base class for vision AI providers."""
    
    @abstractmethod
    async def analyze(self, image_path: Path) -> Dict[str, Any]:
        """Analyze image and return structured results."""
        pass
    
    def _encode_image(self, image_path: Path) -> str:
        """Encode image as base64."""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    
    def _get_media_type(self, image_path: Path) -> str:
        """Get MIME type from extension."""
        media_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        return media_types.get(image_path.suffix.lower(), "image/jpeg")


class OpenAIVision(VisionProvider):
    """OpenAI GPT-4 Vision analysis."""
    
    ANALYSIS_PROMPT = """Analyze this image comprehensively. Provide:

1. Description: 2-3 sentences describing what's in the image
2. Category: One of (Nature, People, Urban, Documents, Art, Food, Technology, Animals, Travel, Other)
3. Detected Objects: List of main objects/subjects visible
4. Extracted Text: Any visible text (OCR)
5. Technical Quality: Score 0-1 for image quality
6. Content Analysis:
   - Indoor/Outdoor
   - Time of day (if determinable)
   - Mood/atmosphere
   - People count (if any)

Respond in JSON format:
{
  "description": "...",
  "category": "...",
  "detected_objects": [...],
  "extracted_text": "...",
  "quality_score": 0.0,
  "content_analysis": {
    "indoor_outdoor": "...",
    "time_of_day": "...",
    "mood": "...",
    "people_count": 0
  }
}"""
    
    def __init__(self, api_key: Optional[str] = None):
        import os
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key required")
    
    async def analyze(self, image_path: Path) -> Dict[str, Any]:
        try:
            from openai import OpenAI
            
            client = OpenAI(api_key=self.api_key)
            image_data = self._encode_image(image_path)
            media_type = self._get_media_type(image_path)
            
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": self.ANALYSIS_PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{media_type};base64,{image_data}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000
            )
            
            # Parse JSON response
            content = response.choices[0].message.content
            
            import json
            # Handle markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            try:
                result = json.loads(content.strip())
            except json.JSONDecodeError:
                result = {"description": content}
            
            result["provider"] = "openai"
            result["model"] = "gpt-4o"
            result["status"] = "completed"
            
            return result
            
        except Exception as e:
            logger.error(f"OpenAI Vision analysis failed: {e}")
            return {
                "status": "failed",
                "provider": "openai",
                "error": str(e),
            }


class ClaudeVision(VisionProvider):
    """Anthropic Claude Vision analysis."""
    
    ANALYSIS_PROMPT = """Analyze this image comprehensively. Provide your analysis in JSON format:

{
  "description": "2-3 sentence description of the image",
  "category": "Nature|People|Urban|Documents|Art|Food|Technology|Animals|Travel|Other",
  "detected_objects": ["list", "of", "objects"],
  "extracted_text": "any visible text or empty string",
  "quality_score": 0.0 to 1.0,
  "content_analysis": {
    "indoor_outdoor": "indoor|outdoor|unclear",
    "time_of_day": "morning|afternoon|evening|night|unclear",
    "mood": "descriptive mood/atmosphere",
    "people_count": 0
  }
}

Respond ONLY with the JSON, no other text."""
    
    def __init__(self, api_key: Optional[str] = None):
        import os
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("Anthropic API key required")
    
    async def analyze(self, image_path: Path) -> Dict[str, Any]:
        try:
            from anthropic import Anthropic
            
            client = Anthropic(api_key=self.api_key)
            image_data = self._encode_image(image_path)
            media_type = self._get_media_type(image_path)
            
            response = client.messages.create(
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
                                "text": self.ANALYSIS_PROMPT
                            }
                        ]
                    }
                ]
            )
            
            content = response.content[0].text
            
            import json
            try:
                result = json.loads(content.strip())
            except json.JSONDecodeError:
                result = {"description": content}
            
            result["provider"] = "claude"
            result["model"] = "claude-sonnet-4-20250514"
            result["status"] = "completed"
            
            return result
            
        except Exception as e:
            logger.error(f"Claude Vision analysis failed: {e}")
            return {
                "status": "failed",
                "provider": "claude",
                "error": str(e),
            }


class LocalVision(VisionProvider):
    """Local BLIP-2 vision analysis (no API cost)."""
    
    def __init__(self, model_name: str = "Salesforce/blip2-opt-2.7b"):
        self.model_name = model_name
        self._model = None
        self._processor = None
    
    def _load_model(self):
        if self._model is None:
            from transformers import Blip2Processor, Blip2ForConditionalGeneration
            import torch
            
            self._processor = Blip2Processor.from_pretrained(self.model_name)
            self._model = Blip2ForConditionalGeneration.from_pretrained(
                self.model_name,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                device_map="auto" if torch.cuda.is_available() else None
            )
    
    async def analyze(self, image_path: Path) -> Dict[str, Any]:
        try:
            import asyncio
            from PIL import Image
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._analyze_sync,
                image_path
            )
            return result
            
        except Exception as e:
            logger.error(f"Local Vision analysis failed: {e}")
            return {
                "status": "failed",
                "provider": "local-blip2",
                "error": str(e),
            }
    
    def _analyze_sync(self, image_path: Path) -> Dict[str, Any]:
        import torch
        from PIL import Image
        
        self._load_model()
        
        image = Image.open(image_path).convert("RGB")
        
        # Generate description
        inputs = self._processor(image, return_tensors="pt")
        if torch.cuda.is_available():
            inputs = inputs.to("cuda", torch.float16)
        
        generated_ids = self._model.generate(**inputs, max_length=100)
        description = self._processor.batch_decode(
            generated_ids, skip_special_tokens=True
        )[0].strip()
        
        return {
            "description": description,
            "category": "Unknown",  # BLIP doesn't categorize
            "detected_objects": [],
            "extracted_text": "",
            "provider": "local-blip2",
            "model": self.model_name,
            "status": "completed",
        }


class VisionAnalyzer:
    """Unified vision analysis interface."""
    
    PROVIDERS = {
        "openai": OpenAIVision,
        "claude": ClaudeVision,
        "local": LocalVision,
        "blip2": LocalVision,
    }
    
    def __init__(self, provider: str = "openai", **kwargs):
        if provider not in self.PROVIDERS:
            raise ValueError(f"Unknown provider: {provider}. Available: {list(self.PROVIDERS.keys())}")
        
        self.provider_name = provider
        self.provider = self.PROVIDERS[provider](**kwargs)
    
    async def analyze(self, image_path: Path) -> Dict[str, Any]:
        """Analyze image."""
        return await self.provider.analyze(image_path)


# Convenience function
async def analyze_image(
    image_path: Path,
    provider: str = "openai",
    **kwargs
) -> Dict[str, Any]:
    """Analyze image with specified provider."""
    analyzer = VisionAnalyzer(provider=provider, **kwargs)
    return await analyzer.analyze(image_path)
