"""SQLite catalog storage for CHIMERA.

This is the main metadata store for all indexed content.
Schema follows PRD Part 3 specification.
"""

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from chimera.config import DEFAULT_CONFIG_DIR
from chimera.utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_DB_PATH = DEFAULT_CONFIG_DIR / "catalog.db"


@dataclass
class FileRecord:
    """A file in the catalog."""
    id: str
    path: str
    filename: str
    extension: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    created_at: datetime | None = None
    modified_at: datetime | None = None
    indexed_at: datetime | None = None
    content_hash: str | None = None
    status: str = "pending"
    error_message: str | None = None
    retry_count: int = 0
    source_id: str | None = None
    word_count: int | None = None
    page_count: int | None = None
    language: str | None = None


@dataclass
class ChunkRecord:
    """A content chunk."""
    id: str
    file_id: str
    chunk_index: int
    content: str
    chunk_type: str | None = None
    embedding_id: str | None = None


@dataclass
class EntityRecord:
    """An extracted entity."""
    id: str
    file_id: str
    entity_type: str
    value: str
    normalized: str | None = None
    confidence: float | None = None
    context: str | None = None
    position: int | None = None


@dataclass
class ImageMetadataRecord:
    """Image metadata from EXIF/GPS/AI analysis."""
    file_id: str
    width: int | None = None
    height: int | None = None
    format: str | None = None
    color_mode: str | None = None
    # EXIF
    camera_make: str | None = None
    camera_model: str | None = None
    lens: str | None = None
    iso: int | None = None
    aperture: str | None = None
    shutter_speed: str | None = None
    focal_length: str | None = None
    date_taken: datetime | None = None
    # GPS
    latitude: float | None = None
    longitude: float | None = None
    altitude: float | None = None
    location_name: str | None = None
    # AI
    ai_description: str | None = None
    ai_categories: list[str] | None = None
    ai_objects: list[str] | None = None
    ai_provider: str | None = None
    # Other
    thumbnail_path: str | None = None
    ocr_text: str | None = None


@dataclass
class AudioMetadataRecord:
    """Audio metadata from file tags and transcription."""
    file_id: str
    duration_seconds: float | None = None
    duration_formatted: str | None = None
    bitrate: int | None = None
    sample_rate: int | None = None
    channels: int | None = None
    codec: str | None = None
    # Tags
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    genre: str | None = None
    year: int | None = None
    track_number: int | None = None
    # Transcription
    transcription_status: str = "pending"
    transcription_text: str | None = None
    transcription_provider: str | None = None


@dataclass
class GPSLocationRecord:
    """GPS location for cross-file correlation."""
    id: str
    file_id: str
    latitude: float
    longitude: float
    location_name: str | None = None
    country: str | None = None
    city: str | None = None
    captured_at: datetime | None = None


class CatalogDB:
    """SQLite database for file and content catalog."""
    
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or DEFAULT_DB_PATH
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path, timeout=60.0)
        cursor = conn.cursor()

        # Enable WAL mode for better concurrent access
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=60000")
        cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache for large DBs
        
        # Sources table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sources (
                id              TEXT PRIMARY KEY,
                path            TEXT NOT NULL UNIQUE,
                name            TEXT,
                priority        TEXT DEFAULT 'medium',
                recursive       BOOLEAN DEFAULT TRUE,
                enabled         BOOLEAN DEFAULT TRUE,
                file_types      TEXT,
                last_scan       DATETIME,
                file_count      INTEGER DEFAULT 0
            )
        """)
        
        # Files table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id              TEXT PRIMARY KEY,
                path            TEXT NOT NULL UNIQUE,
                filename        TEXT NOT NULL,
                extension       TEXT,
                mime_type       TEXT,
                size_bytes      INTEGER,
                created_at      DATETIME,
                modified_at     DATETIME,
                indexed_at      DATETIME,
                content_hash    TEXT,
                status          TEXT DEFAULT 'pending',
                error_message   TEXT,
                retry_count     INTEGER DEFAULT 0,
                source_id       TEXT REFERENCES sources(id),
                word_count      INTEGER,
                page_count      INTEGER,
                language        TEXT
            )
        """)
        
        # Chunks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id              TEXT PRIMARY KEY,
                file_id         TEXT REFERENCES files(id) ON DELETE CASCADE,
                chunk_index     INTEGER,
                content         TEXT NOT NULL,
                chunk_type      TEXT,
                embedding_id    TEXT,
                token_count     INTEGER,
                UNIQUE(file_id, chunk_index)
            )
        """)
        
        # Entities table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                id              TEXT PRIMARY KEY,
                file_id         TEXT REFERENCES files(id) ON DELETE CASCADE,
                entity_type     TEXT NOT NULL,
                value           TEXT NOT NULL,
                normalized      TEXT,
                confidence      REAL,
                context         TEXT,
                position        INTEGER
            )
        """)
        
        # Global entities (merged across files)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS global_entities (
                id              TEXT PRIMARY KEY,
                entity_type     TEXT NOT NULL,
                value           TEXT NOT NULL,
                normalized      TEXT,
                occurrence_count INTEGER DEFAULT 1,
                file_ids        TEXT,
                first_seen      DATETIME,
                last_seen       DATETIME,
                UNIQUE(entity_type, normalized)
            )
        """)
        
        # Code elements table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS code_elements (
                id              TEXT PRIMARY KEY,
                file_id         TEXT REFERENCES files(id) ON DELETE CASCADE,
                element_type    TEXT NOT NULL,
                name            TEXT NOT NULL,
                signature       TEXT,
                docstring       TEXT,
                line_start      INTEGER,
                line_end        INTEGER,
                complexity      INTEGER,
                embedding_id    TEXT
            )
        """)
        
        # Discoveries table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS discoveries (
                id              TEXT PRIMARY KEY,
                discovery_type  TEXT NOT NULL,
                title           TEXT NOT NULL,
                description     TEXT,
                confidence      REAL NOT NULL,
                evidence        TEXT,
                sources         TEXT,
                first_seen      DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_updated    DATETIME DEFAULT CURRENT_TIMESTAMP,
                status          TEXT DEFAULT 'active',
                user_feedback   TEXT,
                graph_node_id   TEXT,
                UNIQUE(discovery_type, title)
            )
        """)
        
        # Relationships table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS relationships (
                id              TEXT PRIMARY KEY,
                source_file_id  TEXT REFERENCES files(id),
                target_file_id  TEXT REFERENCES files(id),
                relationship    TEXT NOT NULL,
                confidence      REAL,
                evidence        TEXT
            )
        """)
        
        # Conversation sources (FAE)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversation_sources (
                id              TEXT PRIMARY KEY,
                provider        TEXT NOT NULL,
                file_path       TEXT NOT NULL,
                file_hash       TEXT NOT NULL,
                imported_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
                conversation_count INTEGER,
                message_count   INTEGER,
                date_range_start DATETIME,
                date_range_end  DATETIME,
                UNIQUE(file_hash)
            )
        """)
        
        # Conversations (FAE)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id              TEXT PRIMARY KEY,
                source_id       TEXT REFERENCES conversation_sources(id),
                provider        TEXT NOT NULL,
                title           TEXT,
                created_at      DATETIME,
                updated_at      DATETIME,
                message_count   INTEGER,
                primary_topic   TEXT,
                topics          TEXT,
                summary         TEXT,
                UNIQUE(provider, id)
            )
        """)
        
        # Messages (FAE)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id              TEXT PRIMARY KEY,
                conversation_id TEXT REFERENCES conversations(id) ON DELETE CASCADE,
                role            TEXT NOT NULL,
                content         TEXT NOT NULL,
                timestamp       DATETIME,
                sequence        INTEGER,
                entities        TEXT,
                UNIQUE(conversation_id, sequence)
            )
        """)
        
        # Audit log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp       DATETIME DEFAULT CURRENT_TIMESTAMP,
                action          TEXT NOT NULL,
                entity_type     TEXT,
                entity_id       TEXT,
                details         TEXT,
                source          TEXT
            )
        """)

        # Image metadata table (multimedia)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS image_metadata (
                file_id         TEXT PRIMARY KEY REFERENCES files(id) ON DELETE CASCADE,
                width           INTEGER,
                height          INTEGER,
                format          TEXT,
                color_mode      TEXT,
                camera_make     TEXT,
                camera_model    TEXT,
                lens            TEXT,
                iso             INTEGER,
                aperture        TEXT,
                shutter_speed   TEXT,
                focal_length    TEXT,
                date_taken      DATETIME,
                latitude        REAL,
                longitude       REAL,
                altitude        REAL,
                location_name   TEXT,
                ai_description  TEXT,
                ai_categories   TEXT,
                ai_objects      TEXT,
                ai_provider     TEXT,
                thumbnail_path  TEXT,
                ocr_text        TEXT
            )
        """)

        # Audio metadata table (multimedia)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audio_metadata (
                file_id             TEXT PRIMARY KEY REFERENCES files(id) ON DELETE CASCADE,
                duration_seconds    REAL,
                duration_formatted  TEXT,
                bitrate             INTEGER,
                sample_rate         INTEGER,
                channels            INTEGER,
                codec               TEXT,
                title               TEXT,
                artist              TEXT,
                album               TEXT,
                genre               TEXT,
                year                INTEGER,
                track_number        INTEGER,
                transcription_status TEXT DEFAULT 'pending',
                transcription_text  TEXT,
                transcription_provider TEXT
            )
        """)

        # GPS locations (for cross-file correlation)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gps_locations (
                id              TEXT PRIMARY KEY,
                file_id         TEXT REFERENCES files(id) ON DELETE CASCADE,
                latitude        REAL NOT NULL,
                longitude       REAL NOT NULL,
                location_name   TEXT,
                country         TEXT,
                city            TEXT,
                captured_at     DATETIME
            )
        """)

        # Indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_path ON files(path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_status ON files(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_extension ON files(extension)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_file ON chunks(file_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_file ON entities(file_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_global_entities_type ON global_entities(entity_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_code_file ON code_elements(file_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_discoveries_type ON discoveries(discovery_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_discoveries_confidence ON discoveries(confidence)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_provider ON conversations(provider)")

        # Multimedia indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_image_camera ON image_metadata(camera_make, camera_model)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_image_location ON image_metadata(latitude, longitude)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_image_date ON image_metadata(date_taken)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audio_artist ON audio_metadata(artist)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audio_album ON audio_metadata(album)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_gps_coords ON gps_locations(latitude, longitude)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_gps_location ON gps_locations(location_name)")

        conn.commit()
        conn.close()
        
        logger.debug(f"Catalog database initialized: {self.db_path}")
    
    def get_connection(self) -> sqlite3.Connection:
        """Get database connection with WAL mode for concurrency."""
        conn = sqlite3.connect(self.db_path, timeout=60.0)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for better concurrent access
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=60000")
        conn.execute("PRAGMA cache_size=-64000")  # 64MB cache for large DBs
        return conn
    
    # ========== File Operations ==========
    
    def add_file(self, file: FileRecord) -> str:
        """Add a file to the catalog."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO files 
            (id, path, filename, extension, mime_type, size_bytes, 
             created_at, modified_at, indexed_at, content_hash, 
             status, error_message, retry_count, source_id,
             word_count, page_count, language)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            file.id, file.path, file.filename, file.extension,
            file.mime_type, file.size_bytes,
            file.created_at.isoformat() if file.created_at else None,
            file.modified_at.isoformat() if file.modified_at else None,
            file.indexed_at.isoformat() if file.indexed_at else None,
            file.content_hash, file.status, file.error_message,
            file.retry_count, file.source_id, file.word_count,
            file.page_count, file.language,
        ))
        
        conn.commit()
        conn.close()
        
        logger.debug(f"Added file: {file.path}")
        return file.id
    
    def get_file(self, file_id: str) -> FileRecord | None:
        """Get a file by ID."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM files WHERE id = ?", (file_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return self._row_to_file(row)
        return None
    
    def get_file_by_path(self, path: str) -> FileRecord | None:
        """Get a file by path."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM files WHERE path = ?", (path,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return self._row_to_file(row)
        return None
    
    def update_file_status(
        self, 
        file_id: str, 
        status: str, 
        error: str | None = None
    ) -> None:
        """Update file status."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if status == "indexed":
            cursor.execute("""
                UPDATE files 
                SET status = ?, indexed_at = ?, error_message = ?
                WHERE id = ?
            """, (status, datetime.now().isoformat(), error, file_id))
        else:
            cursor.execute("""
                UPDATE files 
                SET status = ?, error_message = ?
                WHERE id = ?
            """, (status, error, file_id))
        
        conn.commit()
        conn.close()
    
    def get_pending_files(self, limit: int = 100) -> list[FileRecord]:
        """Get files pending extraction."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM files 
            WHERE status = 'pending' 
            ORDER BY modified_at DESC
            LIMIT ?
        """, (limit,))
        
        files = [self._row_to_file(row) for row in cursor.fetchall()]
        conn.close()
        return files
    
    def _row_to_file(self, row: sqlite3.Row) -> FileRecord:
        """Convert row to FileRecord."""
        return FileRecord(
            id=row["id"],
            path=row["path"],
            filename=row["filename"],
            extension=row["extension"],
            mime_type=row["mime_type"],
            size_bytes=row["size_bytes"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            modified_at=datetime.fromisoformat(row["modified_at"]) if row["modified_at"] else None,
            indexed_at=datetime.fromisoformat(row["indexed_at"]) if row["indexed_at"] else None,
            content_hash=row["content_hash"],
            status=row["status"],
            error_message=row["error_message"],
            retry_count=row["retry_count"],
            source_id=row["source_id"],
            word_count=row["word_count"],
            page_count=row["page_count"],
            language=row["language"],
        )
    
    # ========== Chunk Operations ==========
    
    def add_chunks(self, chunks: list[ChunkRecord]) -> int:
        """Add multiple chunks."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.executemany("""
            INSERT OR REPLACE INTO chunks
            (id, file_id, chunk_index, content, chunk_type, embedding_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [
            (c.id, c.file_id, c.chunk_index, c.content, c.chunk_type, c.embedding_id)
            for c in chunks
        ])
        
        conn.commit()
        count = cursor.rowcount
        conn.close()
        return count
    
    def get_chunks_for_file(self, file_id: str) -> list[ChunkRecord]:
        """Get all chunks for a file."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM chunks 
            WHERE file_id = ? 
            ORDER BY chunk_index
        """, (file_id,))
        
        chunks = [
            ChunkRecord(
                id=row["id"],
                file_id=row["file_id"],
                chunk_index=row["chunk_index"],
                content=row["content"],
                chunk_type=row["chunk_type"],
                embedding_id=row["embedding_id"],
            )
            for row in cursor.fetchall()
        ]
        conn.close()
        return chunks
    
    # ========== Entity Operations ==========
    
    def add_entities(self, entities: list[EntityRecord]) -> int:
        """Add multiple entities."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.executemany("""
            INSERT INTO entities
            (id, file_id, entity_type, value, normalized, confidence, context, position)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (e.id, e.file_id, e.entity_type, e.value, e.normalized, 
             e.confidence, e.context, e.position)
            for e in entities
        ])
        
        conn.commit()
        count = cursor.rowcount
        conn.close()
        return count
    
    def get_entities_for_file(self, file_id: str) -> list[EntityRecord]:
        """Get all entities for a file."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM entities WHERE file_id = ?
        """, (file_id,))
        
        entities = [
            EntityRecord(
                id=row["id"],
                file_id=row["file_id"],
                entity_type=row["entity_type"],
                value=row["value"],
                normalized=row["normalized"],
                confidence=row["confidence"],
                context=row["context"],
                position=row["position"],
            )
            for row in cursor.fetchall()
        ]
        conn.close()
        return entities
    
    # ========== Statistics ==========
    
    def get_stats(self) -> dict[str, Any]:
        """Get catalog statistics."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        stats = {}
        
        # File counts by status
        cursor.execute("""
            SELECT status, COUNT(*) FROM files GROUP BY status
        """)
        stats["files_by_status"] = dict(cursor.fetchall())
        
        # File counts by extension
        cursor.execute("""
            SELECT extension, COUNT(*) FROM files 
            WHERE extension IS NOT NULL
            GROUP BY extension
            ORDER BY COUNT(*) DESC
            LIMIT 10
        """)
        stats["files_by_extension"] = dict(cursor.fetchall())
        
        # Total counts
        cursor.execute("SELECT COUNT(*) FROM files")
        stats["total_files"] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM chunks")
        stats["total_chunks"] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM entities")
        stats["total_entities"] = cursor.fetchone()[0]

        # Entity counts by type
        cursor.execute("""
            SELECT entity_type, COUNT(*) FROM entities
            GROUP BY entity_type
            ORDER BY COUNT(*) DESC
            LIMIT 10
        """)
        stats["entities_by_type"] = dict(cursor.fetchall())

        cursor.execute("SELECT COUNT(*) FROM discoveries WHERE status = 'active'")
        stats["active_discoveries"] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM conversations")
        stats["total_conversations"] = cursor.fetchone()[0]
        
        conn.close()
        return stats
    
    def log_audit(self, action: str, entity_type: str, entity_id: str, details: str | None = None) -> None:
        """Log an audit entry."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO audit_log (action, entity_type, entity_id, details, source)
            VALUES (?, ?, ?, ?, 'daemon')
        """, (action, entity_type, entity_id, details))

        conn.commit()
        conn.close()

    # ========== Multimedia Metadata Operations ==========

    def add_image_metadata(self, record: ImageMetadataRecord) -> None:
        """Add or update image metadata."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO image_metadata
            (file_id, width, height, format, color_mode,
             camera_make, camera_model, lens, iso, aperture,
             shutter_speed, focal_length, date_taken,
             latitude, longitude, altitude, location_name,
             ai_description, ai_categories, ai_objects, ai_provider,
             thumbnail_path, ocr_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record.file_id, record.width, record.height, record.format, record.color_mode,
            record.camera_make, record.camera_model, record.lens, record.iso, record.aperture,
            record.shutter_speed, record.focal_length,
            record.date_taken.isoformat() if record.date_taken else None,
            record.latitude, record.longitude, record.altitude, record.location_name,
            record.ai_description,
            json.dumps(record.ai_categories) if record.ai_categories else None,
            json.dumps(record.ai_objects) if record.ai_objects else None,
            record.ai_provider,
            record.thumbnail_path, record.ocr_text,
        ))

        conn.commit()
        conn.close()
        logger.debug(f"Added image metadata for file: {record.file_id}")

    def get_image_metadata(self, file_id: str) -> ImageMetadataRecord | None:
        """Get image metadata by file ID."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM image_metadata WHERE file_id = ?", (file_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return ImageMetadataRecord(
                file_id=row["file_id"],
                width=row["width"],
                height=row["height"],
                format=row["format"],
                color_mode=row["color_mode"],
                camera_make=row["camera_make"],
                camera_model=row["camera_model"],
                lens=row["lens"],
                iso=row["iso"],
                aperture=row["aperture"],
                shutter_speed=row["shutter_speed"],
                focal_length=row["focal_length"],
                date_taken=datetime.fromisoformat(row["date_taken"]) if row["date_taken"] else None,
                latitude=row["latitude"],
                longitude=row["longitude"],
                altitude=row["altitude"],
                location_name=row["location_name"],
                ai_description=row["ai_description"],
                ai_categories=json.loads(row["ai_categories"]) if row["ai_categories"] else None,
                ai_objects=json.loads(row["ai_objects"]) if row["ai_objects"] else None,
                ai_provider=row["ai_provider"],
                thumbnail_path=row["thumbnail_path"],
                ocr_text=row["ocr_text"],
            )
        return None

    def add_audio_metadata(self, record: AudioMetadataRecord) -> None:
        """Add or update audio metadata."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO audio_metadata
            (file_id, duration_seconds, duration_formatted, bitrate, sample_rate,
             channels, codec, title, artist, album, genre, year, track_number,
             transcription_status, transcription_text, transcription_provider)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record.file_id, record.duration_seconds, record.duration_formatted,
            record.bitrate, record.sample_rate, record.channels, record.codec,
            record.title, record.artist, record.album, record.genre,
            record.year, record.track_number,
            record.transcription_status, record.transcription_text, record.transcription_provider,
        ))

        conn.commit()
        conn.close()
        logger.debug(f"Added audio metadata for file: {record.file_id}")

    def get_audio_metadata(self, file_id: str) -> AudioMetadataRecord | None:
        """Get audio metadata by file ID."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM audio_metadata WHERE file_id = ?", (file_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return AudioMetadataRecord(
                file_id=row["file_id"],
                duration_seconds=row["duration_seconds"],
                duration_formatted=row["duration_formatted"],
                bitrate=row["bitrate"],
                sample_rate=row["sample_rate"],
                channels=row["channels"],
                codec=row["codec"],
                title=row["title"],
                artist=row["artist"],
                album=row["album"],
                genre=row["genre"],
                year=row["year"],
                track_number=row["track_number"],
                transcription_status=row["transcription_status"] or "pending",
                transcription_text=row["transcription_text"],
                transcription_provider=row["transcription_provider"],
            )
        return None

    def add_gps_location(self, record: GPSLocationRecord) -> None:
        """Add a GPS location record."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO gps_locations
            (id, file_id, latitude, longitude, location_name, country, city, captured_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record.id, record.file_id, record.latitude, record.longitude,
            record.location_name, record.country, record.city,
            record.captured_at.isoformat() if record.captured_at else None,
        ))

        conn.commit()
        conn.close()

    def get_multimedia_stats(self) -> dict[str, Any]:
        """Get multimedia statistics for telemetry."""
        conn = self.get_connection()
        cursor = conn.cursor()

        stats = {}

        # Image stats
        cursor.execute("SELECT COUNT(*) FROM image_metadata")
        stats["images_indexed"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM image_metadata WHERE latitude IS NOT NULL")
        stats["images_with_gps"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM image_metadata WHERE ai_description IS NOT NULL")
        stats["images_with_ai"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM image_metadata WHERE ocr_text IS NOT NULL AND ocr_text != ''")
        stats["images_with_ocr"] = cursor.fetchone()[0]

        # Audio stats
        cursor.execute("SELECT COUNT(*) FROM audio_metadata")
        stats["audio_files"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM audio_metadata WHERE transcription_status = 'completed'")
        stats["audio_transcribed"] = cursor.fetchone()[0]

        # GPS stats
        cursor.execute("SELECT COUNT(DISTINCT location_name) FROM gps_locations WHERE location_name IS NOT NULL")
        stats["unique_locations"] = cursor.fetchone()[0]

        # Camera stats
        cursor.execute("""
            SELECT camera_make || ' ' || camera_model AS camera, COUNT(*) as count
            FROM image_metadata
            WHERE camera_make IS NOT NULL
            GROUP BY camera_make, camera_model
            ORDER BY count DESC
            LIMIT 5
        """)
        stats["top_cameras"] = [{"camera": row[0], "count": row[1]} for row in cursor.fetchall()]

        conn.close()
        return stats
