"""Tests for CLI commands."""

import pytest
from click.testing import CliRunner

from chimera.cli import main


@pytest.fixture
def runner():
    """Create CLI runner."""
    return CliRunner()


def test_cli_version(runner):
    """Test --version flag."""
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "chimera" in result.output.lower()


def test_cli_help(runner):
    """Test --help flag."""
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "CHIMERA" in result.output
    assert "serve" in result.output
    assert "status" in result.output
    assert "query" in result.output
    assert "discoveries" in result.output


def test_cli_init(runner, temp_dir, monkeypatch):
    """Test init command."""
    # Mock config directory
    monkeypatch.setattr("chimera.config.DEFAULT_CONFIG_DIR", temp_dir)
    monkeypatch.setattr("chimera.config.DEFAULT_CONFIG_FILE", temp_dir / "chimera.yaml")
    
    result = runner.invoke(main, ["init"])
    assert result.exit_code == 0
    assert "initialized" in result.output.lower()


def test_cli_status_no_daemon(runner):
    """Test status when daemon is not running."""
    result = runner.invoke(main, ["status"])
    # Should show not running message
    assert "not running" in result.output.lower() or result.exit_code == 0


def test_cli_health_no_daemon(runner):
    """Test health when daemon is not running."""
    result = runner.invoke(main, ["health"])
    assert result.exit_code == 1 or "not responding" in result.output.lower()


def test_cli_discoveries_help(runner):
    """Test discoveries command help."""
    result = runner.invoke(main, ["discoveries", "--help"])
    assert result.exit_code == 0
    assert "--type" in result.output
    assert "--min-confidence" in result.output


def test_cli_query_help(runner):
    """Test query command help."""
    result = runner.invoke(main, ["query", "--help"])
    assert result.exit_code == 0
    assert "--limit" in result.output
    assert "--min-score" in result.output


def test_cli_correlate_help(runner):
    """Test correlate command help."""
    result = runner.invoke(main, ["correlate", "--help"])
    assert result.exit_code == 0
    assert "--now" in result.output


def test_cli_graph_export_help(runner):
    """Test graph-export command help."""
    result = runner.invoke(main, ["graph-export", "--help"])
    assert result.exit_code == 0
    assert "--output" in result.output
    assert "--format" in result.output


def test_cli_graph_sync_help(runner):
    """Test graph-sync command help."""
    result = runner.invoke(main, ["graph-sync", "--help"])
    assert result.exit_code == 0
    assert "--repo" in result.output
    assert "--dry-run" in result.output


def test_cli_ask_help(runner):
    """Test ask command help."""
    result = runner.invoke(main, ["ask", "--help"])
    assert result.exit_code == 0
    assert "--context" in result.output


def test_cli_feedback_help(runner):
    """Test feedback command help."""
    result = runner.invoke(main, ["feedback", "--help"])
    assert result.exit_code == 0
    assert "--action" in result.output
    assert "confirm" in result.output
    assert "dismiss" in result.output
