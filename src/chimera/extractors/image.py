"""Image extraction with parallel EXIF, GPS, and thumbnail generation.

Extracts:
- EXIF metadata (camera, settings, timestamps)
- GPS coordinates with reverse geocoding
- Thumbnails (WebP, multiple sizes)
- File hash for deduplication
"""

import asyncio
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

# Supported image extensions
IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", 
    ".bmp", ".tiff", ".tif", ".heic", ".heif"
}


class ImageExtractor:
    """Extract metadata from images with parallel processing."""
    
    SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS
    
    def __init__(self, generate_thumbnails: bool = True, geocode: bool = True):
        self.generate_thumbnails = generate_thumbnails
        self.geocode = geocode
        self._geocoder = None
    
    async def extract(self, file_path: Path) -> Dict[str, Any]:
        """Extract all image data in parallel."""
        
        # Run all extractions concurrently
        tasks = [
            asyncio.create_task(self._extract_exif(file_path)),
            asyncio.create_task(self._compute_hash(file_path)),
            asyncio.create_task(self._get_dimensions(file_path)),
        ]
        
        if self.generate_thumbnails:
            tasks.append(asyncio.create_task(self._generate_thumbnail(file_path)))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Unpack results
        exif_data = results[0] if not isinstance(results[0], Exception) else {}
        file_hash = results[1] if not isinstance(results[1], Exception) else hashlib.md5(str(file_path).encode()).hexdigest()
        dimensions = results[2] if not isinstance(results[2], Exception) else None
        thumbnail_path = results[3] if len(results) > 3 and not isinstance(results[3], Exception) else None
        
        # Extract GPS and geocode if available
        gps_data = None
        if exif_data.get("gps_raw"):
            gps_data = await self._process_gps(exif_data.pop("gps_raw"))
        
        return {
            "id": f"img_{file_hash[:12]}",
            "file_path": str(file_path),
            "file_name": file_path.name,
            "file_type": "image",
            "extension": file_path.suffix.lower(),
            "file_size": file_path.stat().st_size,
            "file_hash": file_hash,
            "dimensions": dimensions,
            "exif": exif_data,
            "gps": gps_data,
            "thumbnail": thumbnail_path,
            "needs_ai_analysis": True,
            "extracted_at": datetime.now().isoformat(),
        }
    
    async def _extract_exif(self, file_path: Path) -> Dict[str, Any]:
        """Extract EXIF metadata."""
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS, GPSTAGS
            
            with Image.open(file_path) as img:
                exif = img._getexif()
                if not exif:
                    return {}
                
                exif_data = {}
                gps_info = {}
                
                for tag_id, value in exif.items():
                    tag = TAGS.get(tag_id, tag_id)
                    
                    # Handle GPS separately
                    if tag == "GPSInfo":
                        for gps_tag_id, gps_value in value.items():
                            gps_tag = GPSTAGS.get(gps_tag_id, gps_tag_id)
                            gps_info[gps_tag] = gps_value
                        continue
                    
                    # Skip binary data
                    if isinstance(value, bytes):
                        continue
                    
                    # Convert special types
                    if hasattr(value, 'numerator'):
                        value = float(value)
                    
                    exif_data[tag] = value
                
                # Organize into categories
                organized = self._organize_exif(exif_data)
                
                # Add raw GPS for later processing
                if gps_info:
                    organized["gps_raw"] = gps_info
                
                return organized
                
        except ImportError:
            logger.warning("PIL not available for EXIF extraction")
            return {}
        except Exception as e:
            logger.debug(f"EXIF extraction failed for {file_path}: {e}")
            return {}
    
    def _organize_exif(self, raw_exif: Dict) -> Dict[str, Any]:
        """Organize raw EXIF into structured categories."""
        
        # Camera info
        camera = {}
        if raw_exif.get("Make"):
            camera["make"] = str(raw_exif["Make"]).strip()
        if raw_exif.get("Model"):
            camera["model"] = str(raw_exif["Model"]).strip()
        if raw_exif.get("LensModel"):
            camera["lens"] = str(raw_exif["LensModel"]).strip()
        if raw_exif.get("Software"):
            camera["software"] = str(raw_exif["Software"]).strip()
        
        # Camera settings
        settings = {}
        if raw_exif.get("ISOSpeedRatings"):
            settings["iso"] = raw_exif["ISOSpeedRatings"]
        if raw_exif.get("FNumber"):
            settings["aperture"] = f"f/{raw_exif['FNumber']}"
        if raw_exif.get("ExposureTime"):
            exp = raw_exif["ExposureTime"]
            if exp < 1:
                settings["shutter_speed"] = f"1/{int(1/exp)}"
            else:
                settings["shutter_speed"] = f"{exp}s"
        if raw_exif.get("FocalLength"):
            settings["focal_length"] = f"{raw_exif['FocalLength']}mm"
        if raw_exif.get("ExposureBiasValue"):
            settings["exposure_bias"] = raw_exif["ExposureBiasValue"]
        if raw_exif.get("Flash"):
            settings["flash"] = raw_exif["Flash"]
        
        # Timestamps
        timestamps = {}
        if raw_exif.get("DateTimeOriginal"):
            timestamps["date_taken"] = raw_exif["DateTimeOriginal"]
        if raw_exif.get("DateTime"):
            timestamps["date_modified"] = raw_exif["DateTime"]
        if raw_exif.get("DateTimeDigitized"):
            timestamps["date_digitized"] = raw_exif["DateTimeDigitized"]
        
        # Image properties
        properties = {}
        if raw_exif.get("Orientation"):
            properties["orientation"] = raw_exif["Orientation"]
        if raw_exif.get("ColorSpace"):
            properties["color_space"] = raw_exif["ColorSpace"]
        if raw_exif.get("WhiteBalance"):
            properties["white_balance"] = raw_exif["WhiteBalance"]
        
        return {
            "camera": camera if camera else None,
            "settings": settings if settings else None,
            "timestamps": timestamps if timestamps else None,
            "properties": properties if properties else None,
        }
    
    async def _process_gps(self, gps_info: Dict) -> Optional[Dict[str, Any]]:
        """Process GPS data and optionally geocode."""
        try:
            lat = self._convert_gps_coord(
                gps_info.get("GPSLatitude"),
                gps_info.get("GPSLatitudeRef")
            )
            lon = self._convert_gps_coord(
                gps_info.get("GPSLongitude"),
                gps_info.get("GPSLongitudeRef")
            )
            
            if lat is None or lon is None:
                return None
            
            gps_data = {
                "latitude": lat,
                "longitude": lon,
            }
            
            # Altitude
            if gps_info.get("GPSAltitude"):
                alt = gps_info["GPSAltitude"]
                if hasattr(alt, 'numerator'):
                    alt = float(alt)
                ref = gps_info.get("GPSAltitudeRef", 0)
                if ref == 1:
                    alt = -alt
                gps_data["altitude"] = alt
            
            # Reverse geocode
            if self.geocode:
                location = await self._geocode_location(lat, lon)
                if location:
                    gps_data["location_name"] = location
            
            return gps_data
            
        except Exception as e:
            logger.debug(f"GPS processing failed: {e}")
            return None
    
    def _convert_gps_coord(self, coord, ref) -> Optional[float]:
        """Convert GPS coordinate to decimal degrees."""
        if not coord or not ref:
            return None
        
        try:
            # Handle tuple of rationals
            def to_float(val):
                if hasattr(val, 'numerator'):
                    return float(val)
                return float(val)
            
            degrees = to_float(coord[0])
            minutes = to_float(coord[1])
            seconds = to_float(coord[2])
            
            decimal = degrees + minutes / 60 + seconds / 3600
            
            if ref in ("S", "W"):
                decimal = -decimal
            
            return round(decimal, 6)
            
        except Exception:
            return None
    
    async def _geocode_location(self, lat: float, lon: float) -> Optional[str]:
        """Reverse geocode coordinates to location name."""
        try:
            from geopy.geocoders import Nominatim
            
            if self._geocoder is None:
                self._geocoder = Nominatim(user_agent="chimera-excavator")
            
            # Run in executor to not block
            loop = asyncio.get_event_loop()
            location = await loop.run_in_executor(
                None,
                lambda: self._geocoder.reverse(f"{lat}, {lon}", language="en")
            )
            
            if location:
                # Extract meaningful parts
                address = location.raw.get("address", {})
                parts = []
                
                # City/town
                for key in ["city", "town", "village", "municipality"]:
                    if address.get(key):
                        parts.append(address[key])
                        break
                
                # State/region
                if address.get("state"):
                    parts.append(address["state"])
                
                # Country
                if address.get("country"):
                    parts.append(address["country"])
                
                if parts:
                    return ", ".join(parts)
                
                return location.address[:100]
            
        except ImportError:
            logger.debug("geopy not available for geocoding")
        except Exception as e:
            logger.debug(f"Geocoding failed: {e}")
        
        return None
    
    async def _generate_thumbnail(self, file_path: Path) -> Optional[str]:
        """Generate WebP thumbnail."""
        try:
            from PIL import Image
            
            # Create thumbnails directory
            thumb_dir = file_path.parent / "thumbnails"
            thumb_dir.mkdir(exist_ok=True)
            
            thumb_name = f"{file_path.stem}_thumb.webp"
            thumb_path = thumb_dir / thumb_name
            
            with Image.open(file_path) as img:
                # Handle EXIF orientation
                try:
                    from PIL import ImageOps
                    img = ImageOps.exif_transpose(img)
                except:
                    pass
                
                # Convert to RGB if necessary
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                
                # Resize
                img.thumbnail((400, 400), Image.Resampling.LANCZOS)
                
                # Save as WebP
                img.save(thumb_path, "WEBP", quality=80)
            
            return str(thumb_path)
            
        except ImportError:
            logger.debug("PIL not available for thumbnail generation")
        except Exception as e:
            logger.debug(f"Thumbnail generation failed: {e}")
        
        return None
    
    async def _compute_hash(self, file_path: Path) -> str:
        """Compute file hash for deduplication."""
        hasher = hashlib.md5()
        
        with open(file_path, "rb") as f:
            # Read in chunks for large files
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        
        return hasher.hexdigest()
    
    async def _get_dimensions(self, file_path: Path) -> Optional[Dict[str, int]]:
        """Get image dimensions."""
        try:
            from PIL import Image
            
            with Image.open(file_path) as img:
                return {
                    "width": img.width,
                    "height": img.height,
                }
        except:
            return None


# Convenience function
async def extract_image(file_path: Path, **kwargs) -> Dict[str, Any]:
    """Extract image metadata."""
    extractor = ImageExtractor(**kwargs)
    return await extractor.extract(file_path)
