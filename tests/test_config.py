"""Tests for configuration module."""

from pathlib import Path

import pytest

from chimera.config import (
    ChimeraConfig,
    ExtractionConfig,
    FAEConfig,
    SourceConfig,
    get_default_config,
    load_config,
    save_config,
)


def test_default_config():
    """Test default configuration."""
    config = get_default_config()
    
    assert config.version == "1.0"
    assert len(config.sources) > 0
    assert config.sources[0].path == "E:\\"
    assert config.fae.enabled is True


def test_source_config():
    """Test source configuration."""
    source = SourceConfig(
        path="/test/path",
        recursive=True,
        file_types=["pdf", "md"],
        priority="high",
    )
    
    assert source.path == "/test/path"
    assert source.recursive is True
    assert "pdf" in source.file_types


def test_fae_config():
    """Test FAE configuration."""
    fae = FAEConfig()
    
    assert fae.enabled is True
    assert fae.auto_detect is True
    assert "claude" in fae.providers
    assert fae.providers["claude"].enabled is True


def test_config_save_load(temp_dir):
    """Test saving and loading configuration."""
    config_path = temp_dir / "test_config.yaml"
    
    # Create config
    config = ChimeraConfig(
        version="1.0",
        sources=[
            SourceConfig(path="/test", file_types=["txt"]),
        ],
    )
    
    # Save
    save_config(config, config_path)
    assert config_path.exists()
    
    # Load
    loaded = load_config(config_path)
    assert loaded.version == "1.0"
    assert len(loaded.sources) == 1
    assert loaded.sources[0].path == "/test"


def test_load_nonexistent_config(temp_dir):
    """Test loading nonexistent config returns defaults."""
    config_path = temp_dir / "nonexistent.yaml"
    config = load_config(config_path)
    
    # Should return default config
    assert config.version == "1.0"
