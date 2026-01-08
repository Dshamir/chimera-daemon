"""Multimedia extraction integration tests.

Tests the end-to-end flow:
1. Image extraction -> ImageMetadataRecord -> catalog storage
2. Audio extraction -> AudioMetadataRecord -> catalog storage
3. GPS location storage
4. Error handling for corrupt/missing files
"""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from chimera.storage.catalog import (
    AudioMetadataRecord,
    CatalogDB,
    GPSLocationRecord,
    ImageMetadataRecord,
)


@pytest.fixture
def temp_catalog():
    """Create a temporary catalog database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "catalog.db"
        catalog = CatalogDB(db_path)
        yield catalog


class TestImageMetadataRecord:
    """Test ImageMetadataRecord dataclass and storage."""

    def test_create_basic_record(self):
        """Test creating a basic image metadata record."""
        record = ImageMetadataRecord(
            file_id="file_123",
            width=1920,
            height=1080,
            format="JPEG",
        )
        assert record.file_id == "file_123"
        assert record.width == 1920
        assert record.height == 1080
        assert record.format == "JPEG"
        assert record.latitude is None  # Optional fields default to None

    def test_create_full_record(self):
        """Test creating a fully populated image record."""
        record = ImageMetadataRecord(
            file_id="file_456",
            width=4032,
            height=3024,
            format="JPEG",
            color_mode="RGB",
            camera_make="Apple",
            camera_model="iPhone 14 Pro",
            lens="iPhone 14 Pro back triple camera",
            iso=100,
            aperture="f/1.78",
            shutter_speed="1/120",
            focal_length="6.86mm",
            date_taken=datetime(2024, 6, 15, 14, 30, 0),
            latitude=40.7128,
            longitude=-74.0060,
            altitude=10.5,
            location_name="New York, NY",
            ai_description="A cityscape photo",
            ai_categories=["urban", "architecture"],
            ai_objects=["building", "sky"],
            ai_provider="openai",
            thumbnail_path="/tmp/thumb_456.jpg",
            ocr_text="Times Square",
        )
        assert record.camera_make == "Apple"
        assert record.latitude == 40.7128
        assert record.ai_description == "A cityscape photo"

    def test_store_and_retrieve_image_metadata(self, temp_catalog):
        """Test storing and retrieving image metadata from catalog."""
        record = ImageMetadataRecord(
            file_id="img_test_001",
            width=800,
            height=600,
            format="PNG",
            camera_make="Canon",
            camera_model="EOS R5",
        )

        # Store
        temp_catalog.add_image_metadata(record)

        # Retrieve
        retrieved = temp_catalog.get_image_metadata("img_test_001")

        assert retrieved is not None
        assert retrieved.file_id == "img_test_001"
        assert retrieved.width == 800
        assert retrieved.height == 600
        assert retrieved.camera_make == "Canon"


class TestAudioMetadataRecord:
    """Test AudioMetadataRecord dataclass and storage."""

    def test_create_basic_record(self):
        """Test creating a basic audio metadata record."""
        record = AudioMetadataRecord(
            file_id="audio_123",
            duration_seconds=180.5,
            duration_formatted="3:00",
        )
        assert record.file_id == "audio_123"
        assert record.duration_seconds == 180.5
        assert record.transcription_status == "pending"  # Default value

    def test_create_full_record(self):
        """Test creating a fully populated audio record."""
        record = AudioMetadataRecord(
            file_id="audio_456",
            duration_seconds=245.0,
            duration_formatted="4:05",
            bitrate=320000,
            sample_rate=44100,
            channels=2,
            codec="mp3",
            title="My Song",
            artist="Test Artist",
            album="Test Album",
            genre="Rock",
            year=2024,
            track_number=1,
            transcription_status="completed",
            transcription_text="Hello, this is a test recording.",
            transcription_provider="whisper",
        )
        assert record.title == "My Song"
        assert record.transcription_status == "completed"

    def test_store_and_retrieve_audio_metadata(self, temp_catalog):
        """Test storing and retrieving audio metadata from catalog."""
        record = AudioMetadataRecord(
            file_id="audio_test_001",
            duration_seconds=120.0,
            duration_formatted="2:00",
            title="Test Track",
            artist="Test Artist",
        )

        # Store
        temp_catalog.add_audio_metadata(record)

        # Retrieve
        retrieved = temp_catalog.get_audio_metadata("audio_test_001")

        assert retrieved is not None
        assert retrieved.file_id == "audio_test_001"
        assert retrieved.duration_seconds == 120.0
        assert retrieved.title == "Test Track"


class TestGPSLocationRecord:
    """Test GPSLocationRecord dataclass and storage."""

    def test_create_gps_record(self):
        """Test creating a GPS location record."""
        record = GPSLocationRecord(
            id="gps_001",
            file_id="file_123",
            latitude=37.7749,
            longitude=-122.4194,
            location_name="San Francisco, CA",
            country="USA",
            city="San Francisco",
            captured_at=datetime(2024, 6, 15, 12, 0, 0),
        )
        assert record.latitude == 37.7749
        assert record.city == "San Francisco"

    def test_store_and_retrieve_gps_location(self, temp_catalog):
        """Test storing and retrieving GPS location from catalog."""
        record = GPSLocationRecord(
            id="gps_test_001",
            file_id="file_test_001",
            latitude=51.5074,
            longitude=-0.1278,
            location_name="London, UK",
            country="UK",
            city="London",
        )

        # Store
        temp_catalog.add_gps_location(record)

        # Retrieve (need to implement get method if not exists)
        conn = temp_catalog.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM gps_locations WHERE id = ?", ("gps_test_001",))
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[2] == 51.5074  # latitude
        assert row[3] == -0.1278  # longitude


class TestPipelineMultimediaIntegration:
    """Test the extraction pipeline's multimedia handling."""

    @pytest.fixture
    def mock_catalog(self):
        """Create a mock catalog for testing."""
        return MagicMock(spec=CatalogDB)

    def test_pipeline_stores_image_metadata_with_record(self, mock_catalog):
        """Test that pipeline constructs ImageMetadataRecord correctly."""
        from chimera.extractors.pipeline import ExtractionPipeline

        pipeline = ExtractionPipeline(catalog=mock_catalog)

        # Simulate image metadata
        metadata = {
            "file_type": "image",
            "dimensions": {"width": 1920, "height": 1080},
            "exif": {
                "camera": {"make": "Sony", "model": "A7III"},
                "settings": {"iso": 400, "aperture": "f/2.8"},
                "timestamps": {"date_taken": "2024:06:15 10:30:00"},
            },
            "gps": {
                "latitude": 40.7128,
                "longitude": -74.0060,
                "location_name": "NYC",
            },
            "ai": {
                "description": "A test image",
                "provider": "openai",
            },
        }

        # Call the method
        pipeline._store_image_metadata(
            file_id="test_file",
            file_path=Path("/test/image.jpg"),
            metadata=metadata,
        )

        # Verify add_image_metadata was called with an ImageMetadataRecord
        mock_catalog.add_image_metadata.assert_called_once()
        call_args = mock_catalog.add_image_metadata.call_args
        record = call_args[0][0]  # First positional argument

        assert isinstance(record, ImageMetadataRecord)
        assert record.file_id == "test_file"
        assert record.width == 1920
        assert record.camera_make == "Sony"
        assert record.latitude == 40.7128

        # Verify GPS location was also stored
        mock_catalog.add_gps_location.assert_called_once()
        gps_record = mock_catalog.add_gps_location.call_args[0][0]
        assert isinstance(gps_record, GPSLocationRecord)
        assert gps_record.latitude == 40.7128

    def test_pipeline_stores_audio_metadata_with_record(self, mock_catalog):
        """Test that pipeline constructs AudioMetadataRecord correctly."""
        from chimera.extractors.pipeline import ExtractionPipeline

        pipeline = ExtractionPipeline(catalog=mock_catalog)

        # Simulate audio metadata
        metadata = {
            "file_type": "audio",
            "duration_seconds": 180.5,
            "duration_formatted": "3:00",
            "bitrate": 320000,
            "sample_rate": 44100,
            "channels": 2,
            "tags": {
                "title": "Test Song",
                "artist": "Test Artist",
                "album": "Test Album",
                "year": "2024",
            },
            "transcription": {
                "status": "completed",
                "text": "Hello world",
                "provider": "whisper",
            },
        }

        # Call the method
        pipeline._store_audio_metadata(
            file_id="test_audio",
            file_path=Path("/test/audio.mp3"),
            metadata=metadata,
        )

        # Verify add_audio_metadata was called with an AudioMetadataRecord
        mock_catalog.add_audio_metadata.assert_called_once()
        call_args = mock_catalog.add_audio_metadata.call_args
        record = call_args[0][0]

        assert isinstance(record, AudioMetadataRecord)
        assert record.file_id == "test_audio"
        assert record.duration_seconds == 180.5
        assert record.title == "Test Song"
        assert record.year == 2024

    def test_pipeline_handles_missing_metadata_gracefully(self, mock_catalog):
        """Test that pipeline handles missing/None metadata fields."""
        from chimera.extractors.pipeline import ExtractionPipeline

        pipeline = ExtractionPipeline(catalog=mock_catalog)

        # Minimal metadata
        metadata = {
            "file_type": "image",
            "dimensions": {},
            "exif": None,
            "gps": None,
        }

        # Should not raise
        pipeline._store_image_metadata(
            file_id="test_minimal",
            file_path=Path("/test/minimal.jpg"),
            metadata=metadata,
        )

        # Verify record was created with None values
        mock_catalog.add_image_metadata.assert_called_once()
        record = mock_catalog.add_image_metadata.call_args[0][0]
        assert record.width is None
        assert record.camera_make is None

        # GPS should NOT be stored if lat/long are missing
        mock_catalog.add_gps_location.assert_not_called()

    def test_pipeline_raises_on_storage_error(self, mock_catalog):
        """Test that pipeline raises errors instead of silently failing."""
        from chimera.extractors.pipeline import ExtractionPipeline

        mock_catalog.add_image_metadata.side_effect = Exception("Database error")

        pipeline = ExtractionPipeline(catalog=mock_catalog)

        metadata = {
            "file_type": "image",
            "dimensions": {"width": 100, "height": 100},
        }

        # Should raise, not silently fail
        with pytest.raises(Exception, match="Database error"):
            pipeline._store_image_metadata(
                file_id="test_error",
                file_path=Path("/test/error.jpg"),
                metadata=metadata,
            )


class TestMultimediaStats:
    """Test multimedia statistics in catalog."""

    def test_get_multimedia_stats(self, temp_catalog):
        """Test retrieving multimedia statistics."""
        # Add some test data
        img_record = ImageMetadataRecord(
            file_id="img1",
            width=1920,
            height=1080,
        )
        temp_catalog.add_image_metadata(img_record)

        audio_record = AudioMetadataRecord(
            file_id="audio1",
            duration_seconds=60.0,
        )
        temp_catalog.add_audio_metadata(audio_record)

        # Get stats
        stats = temp_catalog.get_multimedia_stats()

        # Stats returns flat keys like "images_indexed", "audio_files"
        assert "images_indexed" in stats
        assert "audio_files" in stats
        assert stats["images_indexed"] >= 1
        assert stats["audio_files"] >= 1
