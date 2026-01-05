"""CHIMERA configuration management."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

# Default paths
DEFAULT_CONFIG_DIR = Path.home() / ".chimera"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "chimera.yaml"


class SourceConfig(BaseModel):
    """Configuration for a watched source directory."""
    path: str
    recursive: bool = True
    file_types: list[str] = Field(default_factory=list)
    priority: str = "medium"  # high, medium, low
    enabled: bool = True


class ExcludeConfig(BaseModel):
    """Configuration for excluded paths and patterns."""
    paths: list[str] = Field(default_factory=lambda: [
        "**/node_modules/**",
        "**/.git/**",
        "**/venv/**",
        "**/__pycache__/**",
        "**/AppData/**",
        "**/$RECYCLE.BIN/**",
    ])
    patterns: list[str] = Field(default_factory=lambda: [
        "*.tmp", "*.log", "*.bak", "Thumbs.db", "desktop.ini", ".DS_Store"
    ])
    size_max: str = "100MB"


class ExtractionConfig(BaseModel):
    """Configuration for extraction settings."""
    batch_size: int = 50
    parallel_workers: int = 4
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    ocr_enabled: bool = True
    ocr_languages: list[str] = Field(default_factory=lambda: ["eng"])


class FAEProviderConfig(BaseModel):
    """Configuration for a FAE provider."""
    enabled: bool = True
    extract_artifacts: bool = True


class FAEConfig(BaseModel):
    """Configuration for FAE (Full Archaeology Excavation)."""
    enabled: bool = True
    auto_detect: bool = True
    watch_paths: list[str] = Field(default_factory=list)
    providers: dict[str, FAEProviderConfig] = Field(default_factory=lambda: {
        "claude": FAEProviderConfig(),
        "chatgpt": FAEProviderConfig(),
        "gemini": FAEProviderConfig(),
        "grok": FAEProviderConfig(),
    })
    correlate_on_import: bool = True
    min_confidence_to_surface: float = 0.7


class ScheduleConfig(BaseModel):
    """Configuration for scheduled tasks."""
    full_scan: str = "0 3 * * 0"  # Weekly Sunday 3am
    correlation: str = "0 4 * * *"  # Daily 4am
    discovery: str = "0 5 * * *"  # Daily 5am


class APIConfig(BaseModel):
    """Configuration for API server."""
    host: str = "127.0.0.1"
    port: int = 7777


class PrivacyConfig(BaseModel):
    """Configuration for privacy settings."""
    exclude_patterns: list[str] = Field(default_factory=lambda: [
        "*password*", "*secret*", "*.pem", "*.key"
    ])
    anonymize: list[str] = Field(default_factory=lambda: [
        "phone_numbers", "email_addresses"
    ])
    audit_log: bool = True


class IntegrationConfig(BaseModel):
    """Configuration for external integrations."""
    sif_repo: str = "Dshamir/sif-knowledge-base"
    auto_sync: bool = False


class ChimeraConfig(BaseModel):
    """Main CHIMERA configuration."""
    version: str = "1.0"
    sources: list[SourceConfig] = Field(default_factory=list)
    exclude: ExcludeConfig = Field(default_factory=ExcludeConfig)
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)
    fae: FAEConfig = Field(default_factory=FAEConfig)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    privacy: PrivacyConfig = Field(default_factory=PrivacyConfig)
    integration: IntegrationConfig = Field(default_factory=IntegrationConfig)


def get_default_config() -> ChimeraConfig:
    """Get default configuration with E:\\ as primary source."""
    return ChimeraConfig(
        sources=[
            SourceConfig(
                path="E:\\",
                recursive=True,
                file_types=["pdf", "docx", "md", "txt", "py", "js", "ts", "yaml", "json", "png", "jpg"],
                priority="high",
            ),
            SourceConfig(
                path=str(Path.home() / "Documents"),
                recursive=True,
                file_types=["pdf", "docx", "md", "txt"],
                priority="medium",
            ),
        ],
        fae=FAEConfig(
            watch_paths=["E:\\AI Exports", "E:\\Downloads", str(Path.home() / "Downloads")],
        ),
    )


def load_config(config_path: Path | None = None) -> ChimeraConfig:
    """Load configuration from file or return defaults."""
    if config_path is None:
        config_path = DEFAULT_CONFIG_FILE
    
    if config_path.exists():
        with open(config_path) as f:
            data = yaml.safe_load(f)
            if data:
                return ChimeraConfig.model_validate(data)
    
    return get_default_config()


def save_config(config: ChimeraConfig, config_path: Path | None = None) -> None:
    """Save configuration to file."""
    if config_path is None:
        config_path = DEFAULT_CONFIG_FILE
    
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(config_path, "w") as f:
        yaml.dump(config.model_dump(), f, default_flow_style=False, sort_keys=False)


def ensure_config_dir() -> Path:
    """Ensure ~/.chimera directory exists and return path."""
    DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    # Create subdirectories
    (DEFAULT_CONFIG_DIR / "vectors").mkdir(exist_ok=True)
    (DEFAULT_CONFIG_DIR / "cache" / "extracted").mkdir(parents=True, exist_ok=True)
    (DEFAULT_CONFIG_DIR / "cache" / "chunks").mkdir(exist_ok=True)
    (DEFAULT_CONFIG_DIR / "cache" / "thumbnails").mkdir(exist_ok=True)
    (DEFAULT_CONFIG_DIR / "logs").mkdir(exist_ok=True)
    (DEFAULT_CONFIG_DIR / "exports" / "claude").mkdir(parents=True, exist_ok=True)
    
    return DEFAULT_CONFIG_DIR
