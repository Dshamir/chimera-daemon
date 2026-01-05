"""Image extractor with OCR support."""

from pathlib import Path

from chimera.extractors.base import BaseExtractor, ExtractionResult
from chimera.utils.logging import get_logger

logger = get_logger(__name__)


class ImageExtractor(BaseExtractor):
    """Extract text from images using OCR."""
    
    name = "image"
    extensions = ["png", "jpg", "jpeg", "gif", "bmp", "tiff", "webp"]
    mime_types = ["image/png", "image/jpeg", "image/gif", "image/bmp", "image/tiff", "image/webp"]
    
    async def extract(self, file_path: Path) -> ExtractionResult:
        """Extract text from image using Tesseract OCR."""
        try:
            import pytesseract
            from PIL import Image
            
            image = Image.open(file_path)
            
            # Get image metadata
            width, height = image.size
            
            # Run OCR
            try:
                text = pytesseract.image_to_string(image)
            except Exception as ocr_error:
                logger.warning(f"OCR failed for {file_path}: {ocr_error}")
                text = ""
            
            # Classify image type
            image_type = self._classify_image(file_path, text)
            
            return ExtractionResult(
                file_path=file_path,
                content=text.strip(),
                metadata={
                    "width": width,
                    "height": height,
                    "format": image.format,
                    "mode": image.mode,
                    "image_type": image_type,
                    "has_text": bool(text.strip()),
                },
                word_count=self.count_words(text),
            )
        except Exception as e:
            logger.error(f"Image extraction failed: {file_path}: {e}")
            return ExtractionResult(
                file_path=file_path,
                content="",
                success=False,
                error=str(e),
            )
    
    def _classify_image(self, file_path: Path, ocr_text: str) -> str:
        """Classify image type based on content and name."""
        name = file_path.name.lower()
        
        # Check for screenshots
        if "screenshot" in name or "screen" in name or "capture" in name:
            return "screenshot"
        
        # Check for diagrams
        if any(word in name for word in ["diagram", "chart", "flow", "graph", "architecture"]):
            return "diagram"
        
        # Check based on OCR content density
        if ocr_text:
            word_count = len(ocr_text.split())
            if word_count > 50:
                return "document_scan"
            elif word_count > 10:
                return "screenshot"
        
        return "photo"
