"""CHIMERA configuration management."""

import os
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
    max_depth: int | None = None  # None = unlimited, 3 = max 3 levels deep
    file_types: list[str] = Field(default_factory=list)
    priority: str = "medium"  # high, medium, low
    enabled: bool = True
    follow_symlinks: bool = False  # Safety default


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


class APIKeysConfig(BaseModel):
    """Configuration for API keys (config file with env var fallback)."""
    openai: str | None = None
    anthropic: str | None = None
    google: str | None = None

    def model_post_init(self, __context: Any) -> None:
        """Apply environment variable fallbacks."""
        if self.openai is None:
            self.openai = os.getenv("OPENAI_API_KEY")
        if self.anthropic is None:
            self.anthropic = os.getenv("ANTHROPIC_API_KEY")
        if self.google is None:
            self.google = os.getenv("GOOGLE_API_KEY")

    def get_key(self, provider: str) -> str | None:
        """Get API key for provider (config > env var)."""
        key = getattr(self, provider, None)
        if key:
            return key
        # Fallback to env var with various naming conventions
        env_names = [
            f"{provider.upper()}_API_KEY",
            f"{provider.upper()}_KEY",
            f"API_KEY_{provider.upper()}",
        ]
        for name in env_names:
            key = os.getenv(name)
            if key:
                return key
        return None


class VisionConfig(BaseModel):
    """Configuration for AI vision providers."""
    provider: str = "openai"  # openai, claude, local, blip2
    fallback_providers: list[str] = Field(default_factory=lambda: ["claude", "local"])
    timeout: int = 30
    max_retries: int = 3
    local_model: str = "Salesforce/blip2-opt-2.7b"
    enabled: bool = True


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
    vision: VisionConfig = Field(default_factory=VisionConfig)
    api_keys: APIKeysConfig = Field(default_factory=APIKeysConfig)


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


def get_config_path() -> Path:
    """Get the config file path."""
    return DEFAULT_CONFIG_FILE


def get_nested_value(config: ChimeraConfig, key: str) -> Any:
    """Get a nested config value using dotted key notation.

    Examples:
        get_nested_value(config, "vision.provider")  -> "openai"
        get_nested_value(config, "sources.0.path")   -> "E:\\"
        get_nested_value(config, "api_keys.openai")  -> "sk-xxx"
    """
    parts = key.split(".")
    obj: Any = config

    for part in parts:
        if isinstance(obj, list):
            try:
                obj = obj[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(obj, dict):
            obj = obj.get(part)
        elif hasattr(obj, part):
            obj = getattr(obj, part)
        elif hasattr(obj, "model_dump"):
            # Pydantic model
            obj = obj.model_dump().get(part)
        else:
            return None

        if obj is None:
            return None

    return obj


def set_nested_value(config: ChimeraConfig, key: str, value: str) -> None:
    """Set a nested config value using dotted key notation.

    Examples:
        set_nested_value(config, "vision.provider", "claude")
        set_nested_value(config, "sources.0.max_depth", "5")
        set_nested_value(config, "api_keys.openai", "sk-xxx")

    Note: Values are automatically coerced to the correct type.
    """
    parts = key.split(".")
    obj: Any = config

    # Navigate to parent object
    for part in parts[:-1]:
        if isinstance(obj, list):
            obj = obj[int(part)]
        elif hasattr(obj, part):
            obj = getattr(obj, part)
        else:
            raise KeyError(f"Invalid config key: {key}")

    # Set the final value
    final_key = parts[-1]

    # Coerce value type based on existing field type
    if hasattr(obj, final_key):
        current = getattr(obj, final_key)
        if isinstance(current, bool):
            value = value.lower() in ("true", "1", "yes", "on")
        elif isinstance(current, int):
            value = int(value)
        elif isinstance(current, float):
            value = float(value)
        elif current is None:
            # Try to infer type
            if value.lower() in ("true", "false"):
                value = value.lower() == "true"
            elif value.isdigit():
                value = int(value)

        setattr(obj, final_key, value)
    else:
        raise KeyError(f"Invalid config key: {key}")


def test_api_keys(provider: str = "all") -> dict[str, bool]:
    """Test API key configuration.

    Args:
        provider: Provider name or "all" to test all.

    Returns:
        Dict of provider -> is_configured (bool)
    """
    config = load_config()
    results = {}

    providers_to_test = ["openai", "anthropic", "google"] if provider == "all" else [provider]

    for p in providers_to_test:
        key = config.api_keys.get_key(p)
        # Key is "configured" if it exists and has minimum length
        results[p] = key is not None and len(key) > 10

    return results
