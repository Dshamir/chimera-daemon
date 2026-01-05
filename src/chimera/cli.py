"""CHIMERA CLI entry point."""

import sys
from pathlib import Path

import click
import httpx
from rich.console import Console
from rich.table import Table

from chimera import __version__
from chimera.config import ensure_config_dir, get_default_config, load_config, save_config

console = Console()

DEFAULT_API_URL = "http://127.0.0.1:7777"


def api_request(method: str, endpoint: str, **kwargs) -> dict | None:
    """Make API request to daemon."""
    url = f"{DEFAULT_API_URL}{endpoint}"
    try:
        response = httpx.request(method, url, timeout=10, **kwargs)
        return response.json()
    except httpx.ConnectError:
        return None
    except Exception as e:
        console.print(f"[red]API error: {e}[/red]")
        return None


@click.group()
@click.version_option(version=__version__, prog_name="chimera")
def main() -> None:
    """CHIMERA: Cognitive History Integration & Memory Extraction Runtime Agent.
    
    Surface what you know but don't know you know — automatically, continuously, sovereignly.
    """
    pass


@main.command()
@click.option("--dev", is_flag=True, help="Run in development mode")
@click.option("--host", default="127.0.0.1", help="API host")
@click.option("--port", default=7777, type=int, help="API port")
def serve(dev: bool, host: str, port: int) -> None:
    """Start the CHIMERA daemon."""
    console.print(f"[bold green]Starting CHIMERA daemon v{__version__}[/bold green]")
    console.print(f"  Host: {host}")
    console.print(f"  Port: {port}")
    console.print(f"  Dev mode: {dev}")
    console.print()
    
    from chimera.daemon import run_daemon
    run_daemon(host=host, port=port, dev_mode=dev)


@main.command()
def status() -> None:
    """Show CHIMERA daemon status."""
    result = api_request("GET", "/api/v1/status")
    
    if result is None:
        console.print("[red]CHIMERA daemon is not running.[/red]")
        console.print("\nStart with: [cyan]chimera serve[/cyan]")
        return
    
    if result.get("error"):
        console.print(f"[red]{result['error']}[/red]")
        return
    
    console.print("[bold green]CHIMERA Status[/bold green]")
    console.print("─" * 50)
    
    table = Table(show_header=False, box=None)
    table.add_column("Key", style="cyan")
    table.add_column("Value")
    
    table.add_row("Version", result.get("version", "unknown"))
    table.add_row("Running", "✅" if result.get("running") else "❌")
    table.add_row("Uptime", f"{result.get('uptime_seconds', 0):.1f}s")
    table.add_row("Dev Mode", "✅" if result.get("dev_mode") else "❌")
    
    stats = result.get("stats", {})
    table.add_row("", "")
    table.add_row("Files Detected", str(stats.get("files_detected", 0)))
    table.add_row("Jobs Processed", str(stats.get("jobs_processed", 0)))
    table.add_row("Jobs Failed", str(stats.get("jobs_failed", 0)))
    
    config = result.get("config", {})
    table.add_row("", "")
    table.add_row("Sources", str(config.get("sources", 0)))
    table.add_row("FAE Enabled", "✅" if config.get("fae_enabled") else "❌")
    table.add_row("API Port", str(config.get("api_port", 7777)))
    
    console.print(table)


@main.command()
def health() -> None:
    """Check daemon health."""
    result = api_request("GET", "/api/v1/health")
    
    if result is None:
        console.print("[red]❌ CHIMERA daemon is not responding.[/red]")
        sys.exit(1)
    
    if result.get("status") == "healthy":
        console.print(f"[green]✅ CHIMERA daemon is healthy (v{result.get('version')})[/green]")
    else:
        console.print(f"[yellow]⚠️ Status: {result.get('status')}[/yellow]")


@main.command()
@click.argument("query_text")
@click.option("--limit", "-n", default=10, help="Maximum results")
def query(query_text: str, limit: int) -> None:
    """Search the knowledge base with natural language."""
    result = api_request("GET", f"/api/v1/query?q={query_text}&limit={limit}")
    
    if result is None:
        console.print("[red]Daemon not running. Start with: chimera serve[/red]")
        return
    
    if result.get("message"):
        console.print(f"[yellow]{result['message']}[/yellow]")
    
    results = result.get("results", [])
    if results:
        console.print(f"\n[bold]Results for: {query_text}[/bold]")
        for i, r in enumerate(results, 1):
            console.print(f"  {i}. {r}")
    else:
        console.print("No results found.")


@main.command()
@click.option("--files", is_flag=True, help="Excavate files only")
@click.option("--fae", is_flag=True, help="Excavate AI exports only (FAE)")
@click.option("--correlate", is_flag=True, help="Run correlation after excavation")
@click.argument("paths", nargs=-1)
def excavate(files: bool, fae: bool, correlate: bool, paths: tuple) -> None:
    """Trigger cognitive archaeology excavation.
    
    Without flags, excavates everything: files + FAE + correlate.
    """
    if not files and not fae:
        # Default: everything
        files = True
        fae = True
        correlate = True
    
    console.print("[bold]Starting Excavation[/bold]")
    console.print("─" * 40)
    if files:
        console.print("  📁 Files: [green]enabled[/green]")
    if fae:
        console.print("  🤖 FAE (AI exports): [green]enabled[/green]")
    if correlate:
        console.print("  🔗 Correlation: [green]enabled[/green]")
    if paths:
        console.print(f"  📍 Paths: {', '.join(paths)}")
    
    result = api_request("POST", "/api/v1/excavate", json={
        "files": files,
        "fae": fae,
        "correlate": correlate,
        "paths": list(paths) if paths else None,
    })
    
    if result is None:
        console.print("\n[red]Daemon not running. Start with: chimera serve[/red]")
        return
    
    if result.get("status") == "queued":
        console.print(f"\n[green]✅ Excavation queued. Job ID: {result.get('job_id')}[/green]")
    else:
        console.print(f"\n[red]Error: {result.get('error', 'Unknown error')}[/red]")


@main.command(name="fae")
@click.argument("path", required=False)
@click.option("--provider", type=click.Choice(["auto", "claude", "chatgpt", "gemini", "grok"]), default="auto")
@click.option("--recursive", "-r", is_flag=True, help="Process directory recursively")
@click.option("--correlate/--no-correlate", default=True, help="Run correlation after FAE")
def fae_command(path: str | None, provider: str, recursive: bool, correlate: bool) -> None:
    """Process AI conversation exports (Full Archaeology Excavation).
    
    Auto-detects provider format unless --provider specified.
    """
    console.print("[bold]FAE — Full Archaeology Excavation[/bold]")
    console.print("─" * 40)
    console.print(f"  Provider: {provider}")
    if path:
        console.print(f"  Path: {path}")
    console.print(f"  Recursive: {recursive}")
    console.print(f"  Correlate: {correlate}")
    
    result = api_request("POST", "/api/v1/fae", json={
        "path": path or "default",
        "provider": provider,
        "recursive": recursive,
        "correlate": correlate,
    })
    
    if result is None:
        console.print("\n[red]Daemon not running. Start with: chimera serve[/red]")
        return
    
    if result.get("status") == "queued":
        console.print(f"\n[green]✅ FAE queued. Job ID: {result.get('job_id')}[/green]")
    else:
        console.print(f"\n[red]Error: {result.get('error', 'Unknown error')}[/red]")


@main.command()
@click.option("--type", "discovery_type", help="Filter by discovery type")
@click.option("--min-confidence", default=0.7, help="Minimum confidence threshold")
def discoveries(discovery_type: str | None, min_confidence: float) -> None:
    """List surfaced discoveries."""
    params = f"min_confidence={min_confidence}"
    if discovery_type:
        params += f"&discovery_type={discovery_type}"
    
    result = api_request("GET", f"/api/v1/discoveries?{params}")
    
    if result is None:
        console.print("[red]Daemon not running. Start with: chimera serve[/red]")
        return
    
    if result.get("message"):
        console.print(f"[yellow]{result['message']}[/yellow]")
    
    discoveries_list = result.get("discoveries", [])
    if discoveries_list:
        console.print(f"\n[bold]Discoveries (confidence >= {min_confidence})[/bold]")
        for d in discoveries_list:
            console.print(f"  [{d.get('confidence', 0):.2f}] {d.get('title')}")
    else:
        console.print("No discoveries found.")


@main.command()
def config() -> None:
    """Show current configuration."""
    cfg = load_config()
    
    console.print("[bold]CHIMERA Configuration[/bold]")
    console.print("─" * 50)
    
    console.print(f"\n[cyan]Version:[/cyan] {cfg.version}")
    
    console.print(f"\n[cyan]Sources ({len(cfg.sources)}):[/cyan]")
    for s in cfg.sources:
        status = "✅" if s.enabled else "❌"
        console.print(f"  {status} {s.path} ({s.priority})")
        if s.file_types:
            console.print(f"      Types: {', '.join(s.file_types)}")
    
    console.print(f"\n[cyan]FAE:[/cyan]")
    console.print(f"  Enabled: {'\u2705' if cfg.fae.enabled else '\u274c'}")
    console.print(f"  Auto-detect: {'\u2705' if cfg.fae.auto_detect else '\u274c'}")
    if cfg.fae.watch_paths:
        console.print(f"  Watch paths: {', '.join(cfg.fae.watch_paths)}")
    
    console.print(f"\n[cyan]API:[/cyan]")
    console.print(f"  {cfg.api.host}:{cfg.api.port}")
    
    console.print(f"\n[cyan]Privacy:[/cyan]")
    console.print(f"  Audit log: {'\u2705' if cfg.privacy.audit_log else '\u274c'}")


@main.command()
def init() -> None:
    """Initialize CHIMERA configuration."""
    console.print("[bold]Initializing CHIMERA...[/bold]")
    
    # Ensure directory structure
    config_dir = ensure_config_dir()
    console.print(f"  Created: {config_dir}")
    
    # Check for existing config
    from chimera.config import DEFAULT_CONFIG_FILE
    
    if DEFAULT_CONFIG_FILE.exists():
        console.print(f"  Config already exists: {DEFAULT_CONFIG_FILE}")
    else:
        # Create default config
        cfg = get_default_config()
        save_config(cfg)
        console.print(f"  Created: {DEFAULT_CONFIG_FILE}")
    
    console.print("\n[green]✅ CHIMERA initialized.[/green]")
    console.print("\nNext steps:")
    console.print("  1. Edit ~/.chimera/chimera.yaml to configure sources")
    console.print("  2. Run [cyan]chimera serve[/cyan] to start the daemon")
    console.print("  3. Run [cyan]chimera status[/cyan] to check status")


@main.command()
def jobs() -> None:
    """Show job queue statistics."""
    result = api_request("GET", "/api/v1/jobs")
    
    if result is None:
        console.print("[red]Daemon not running. Start with: chimera serve[/red]")
        return
    
    if result.get("error"):
        console.print(f"[red]{result['error']}[/red]")
        return
    
    console.print("[bold]Job Queue[/bold]")
    console.print("─" * 40)
    console.print(f"Pending: {result.get('pending', 0)}")
    
    stats = result.get("stats", {})
    
    if stats.get("by_status"):
        console.print("\n[cyan]By Status:[/cyan]")
        for status, count in stats["by_status"].items():
            console.print(f"  {status}: {count}")
    
    if stats.get("by_type"):
        console.print("\n[cyan]By Type:[/cyan]")
        for job_type, count in stats["by_type"].items():
            console.print(f"  {job_type}: {count}")
    
    if stats.get("recent_failures", 0) > 0:
        console.print(f"\n[yellow]Recent failures (1h): {stats['recent_failures']}[/yellow]")


@main.command()
def logs() -> None:
    """Show recent daemon logs."""
    from chimera.config import DEFAULT_CONFIG_DIR
    
    log_file = DEFAULT_CONFIG_DIR / "logs" / "chimerad.log"
    
    if not log_file.exists():
        console.print("[yellow]No log file found. Is the daemon running?[/yellow]")
        return
    
    # Show last 50 lines
    with open(log_file) as f:
        lines = f.readlines()[-50:]
    
    console.print("[bold]Recent Logs[/bold]")
    console.print("─" * 60)
    for line in lines:
        console.print(line.rstrip())


if __name__ == "__main__":
    main()
