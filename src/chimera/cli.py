"""CHIMERA CLI entry point."""

import json
import sys
import time
from pathlib import Path

import click
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from chimera import __version__
from chimera.config import (
    ensure_config_dir,
    get_config_path,
    get_default_config,
    get_nested_value,
    load_config,
    save_config,
    set_nested_value,
    test_api_keys,
)

console = Console()

DEFAULT_API_URL = "http://127.0.0.1:7777"


def api_request(method: str, endpoint: str, **kwargs) -> dict | None:
    """Make API request to daemon."""
    url = f"{DEFAULT_API_URL}{endpoint}"
    try:
        response = httpx.request(method, url, timeout=30, **kwargs)
        return response.json()
    except httpx.ConnectError:
        return None
    except httpx.TimeoutException:
        console.print(f"[yellow]⚠ Request timed out[/yellow]")
        return None
    except Exception as e:
        console.print(f"[red]✗ API error: {e}[/red]")
        return None


def api_request_with_spinner(method: str, endpoint: str, message: str, **kwargs) -> tuple[dict | None, str | None]:
    """Make API request with spinner and error handling."""
    url = f"{DEFAULT_API_URL}{endpoint}"
    try:
        with console.status(f"[cyan]{message}[/cyan]", spinner="dots"):
            response = httpx.request(method, url, timeout=30, **kwargs)
            result = response.json()

            if response.status_code >= 400:
                return None, f"HTTP {response.status_code}: {result.get('error', 'Unknown')}"

            if result.get("error"):
                return None, result["error"]

            return result, None

    except httpx.ConnectError:
        return None, "Cannot connect to daemon. Is it running?"
    except httpx.TimeoutException:
        return None, "Request timed out"
    except Exception as e:
        return None, str(e)


def is_daemon_running() -> bool:
    """Check if daemon is running."""
    try:
        response = httpx.get(f"{DEFAULT_API_URL}/api/v1/health", timeout=10)
        return response.status_code == 200
    except Exception:
        return False


def daemon_status_dot() -> str:
    """Return colored dot indicating daemon status."""
    return "[green]●[/green]" if is_daemon_running() else "[red]●[/red]"


def print_daemon_status_line() -> None:
    """Print a single line showing daemon status."""
    if is_daemon_running():
        console.print("[green]● Daemon running[/green]")
    else:
        console.print("[red]● Daemon stopped[/red]")


def print_success(message: str) -> None:
    """Print success message."""
    console.print(f"[green]✓[/green] {message}")


def print_error(message: str, detail: str | None = None) -> None:
    """Print error message."""
    console.print(f"[red]✗[/red] {message}")
    if detail:
        console.print(f"  [dim]{detail}[/dim]")


def print_warning(message: str) -> None:
    """Print warning message."""
    console.print(f"[yellow]⚠[/yellow] {message}")


def print_info(message: str) -> None:
    """Print info message."""
    console.print(f"[blue]ℹ[/blue] {message}")


@click.group()
@click.version_option(version=__version__, prog_name="chimera")
def main() -> None:
    """CHIMERA: Cognitive History Integration & Memory Extraction Runtime Agent.
    
    Surface what you know but don't know you know.
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
def shell() -> None:
    """Start the interactive CHIMERA shell.

    The shell provides an interactive interface with auto-starting daemon,
    command history, and tab completion.
    """
    from chimera.shell import main as shell_main
    shell_main()


@main.command()
def stop() -> None:
    """Stop the CHIMERA daemon."""
    if not is_daemon_running():
        print_error("Daemon is not running")
        return

    with console.status("[yellow]Stopping daemon...[/yellow]", spinner="dots") as status:
        result = api_request("POST", "/api/v1/shutdown")

        if result and result.get("status") == "shutting_down":
            # Wait for daemon to stop
            for i in range(20):
                time.sleep(0.5)
                status.update(f"[yellow]Stopping daemon{'.' * (i % 4)}[/yellow]")
                if not is_daemon_running():
                    break

    if not is_daemon_running():
        print_success("Daemon stopped")
    else:
        print_warning("Daemon may still be shutting down...")


@main.command()
@click.option("--dev", is_flag=True, help="Run in development mode")
@click.option("--host", default="127.0.0.1", help="API host")
@click.option("--port", default=7777, type=int, help="API port")
def restart(dev: bool, host: str, port: int) -> None:
    """Restart the CHIMERA daemon."""
    was_running = is_daemon_running()

    if was_running:
        with console.status("[yellow]Stopping daemon...[/yellow]", spinner="dots") as status:
            api_request("POST", "/api/v1/shutdown")

            # Wait for daemon to stop
            for i in range(20):
                time.sleep(0.5)
                status.update(f"[yellow]Stopping daemon{'.' * (i % 4)}[/yellow]")
                if not is_daemon_running():
                    break

        if is_daemon_running():
            print_error("Failed to stop daemon")
            console.print("Try: [cyan]chimera stop[/cyan]")
            return

        print_success("Daemon stopped")
        time.sleep(1)  # Brief pause before restart
    else:
        print_info("Daemon was not running")

    console.print()
    console.print(f"[bold green]Starting CHIMERA daemon v{__version__}[/bold green]")
    console.print(f"  Host: {host}")
    console.print(f"  Port: {port}")
    console.print(f"  Dev mode: {dev}")
    console.print()

    from chimera.daemon import run_daemon
    run_daemon(host=host, port=port, dev_mode=dev)


@main.command()
def ping() -> None:
    """Quick check if daemon is running (shows colored dot)."""
    print_daemon_status_line()


@main.command()
@click.option("--refresh", "-r", default=1.0, help="Refresh rate in seconds")
def dashboard(refresh: float) -> None:
    """Launch real-time telemetry dashboard."""
    if not is_daemon_running():
        print_error("Daemon is not running")
        console.print("Start with: [cyan]chimera serve[/cyan]")
        return

    print_info("Launching telemetry dashboard...")
    print_info("Press Ctrl+C to exit")
    console.print()

    try:
        from chimera.telemetry import run_dashboard
        run_dashboard(refresh_rate=refresh)
    except ImportError as e:
        print_error("Failed to import telemetry module", str(e))
    except KeyboardInterrupt:
        console.print("\n")
        print_info("Dashboard closed")


@main.command()
def status() -> None:
    """Show CHIMERA daemon status."""
    result = api_request("GET", "/api/v1/status")

    if result is None:
        console.print(f"[red]●[/red] [bold]CHIMERA[/bold] — [red]Daemon not running[/red]")
        console.print("\nStart with: [cyan]chimera serve[/cyan]")
        return

    if result.get("error"):
        console.print(f"[red]●[/red] [bold]CHIMERA[/bold] — [red]{result['error']}[/red]")
        return

    console.print(Panel.fit(f"[green]●[/green] [bold]CHIMERA Status[/bold]", border_style="green"))
    
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="cyan")
    table.add_column("Value")
    
    table.add_row("Version", result.get("version", "unknown"))
    table.add_row("Running", "✅" if result.get("running") else "❌")
    
    uptime = result.get('uptime_seconds', 0)
    if uptime > 3600:
        uptime_str = f"{uptime/3600:.1f}h"
    elif uptime > 60:
        uptime_str = f"{uptime/60:.1f}m"
    else:
        uptime_str = f"{uptime:.0f}s"
    table.add_row("Uptime", uptime_str)
    
    stats = result.get("stats", {})
    table.add_row("", "")
    table.add_row("📁 Files Indexed", str(stats.get("files_indexed", 0)))
    table.add_row("📊 Jobs Processed", str(stats.get("jobs_processed", 0)))
    table.add_row("🔗 Correlations Run", str(stats.get("correlations_run", 0)))
    table.add_row("💡 Discoveries", str(stats.get("discoveries_surfaced", 0)))
    
    catalog = result.get("catalog", {})
    if catalog:
        table.add_row("", "")
        table.add_row("🗄️  Total Files", str(catalog.get("total_files", 0)))
        table.add_row("🧩 Total Chunks", str(catalog.get("total_chunks", 0)))
        table.add_row("🏷️  Total Entities", str(catalog.get("total_entities", 0)))
    
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
@click.option("--min-score", default=0.5, help="Minimum similarity score")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def query(query_text: str, limit: int, min_score: float, as_json: bool) -> None:
    """Search the knowledge base with natural language."""
    result = api_request("GET", f"/api/v1/query?q={query_text}&limit={limit}&min_confidence={min_score}")
    
    if result is None:
        console.print("[red]Daemon not running. Start with: chimera serve[/red]")
        return
    
    if as_json:
        console.print(json.dumps(result, indent=2))
        return
    
    results = result.get("results", [])
    if not results:
        console.print(f"[yellow]No results for: {query_text}[/yellow]")
        return
    
    console.print(Panel.fit(f"[bold]Results for: {query_text}[/bold]", border_style="blue"))
    
    for i, r in enumerate(results, 1):
        similarity = r.get("similarity", 0)
        file_path = r.get("file_path", "unknown")
        content = r.get("content", "")[:200]
        
        # Color based on similarity
        if similarity >= 0.8:
            score_color = "green"
        elif similarity >= 0.6:
            score_color = "yellow"
        else:
            score_color = "dim"
        
        console.print(f"\n[{score_color}]{i}. [{similarity:.2f}][/{score_color}] [cyan]{Path(file_path).name}[/cyan]")
        console.print(f"   [dim]{file_path}[/dim]")
        console.print(f"   {content}..." if len(content) == 200 else f"   {content}")


@main.command()
@click.option("--type", "discovery_type", help="Filter by type (expertise, relationship, workflow, skill)")
@click.option("--min-confidence", default=0.7, help="Minimum confidence threshold")
@click.option("--status", "filter_status", type=click.Choice(["active", "confirmed", "dismissed", "all"]), default="active")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def discoveries(discovery_type: str | None, min_confidence: float, filter_status: str, as_json: bool) -> None:
    """List surfaced discoveries (unknown knowns)."""
    params = f"min_confidence={min_confidence}"
    if discovery_type:
        params += f"&discovery_type={discovery_type}"
    if filter_status and filter_status != "all":
        params += f"&status={filter_status}"
    
    result = api_request("GET", f"/api/v1/discoveries?{params}")
    
    if result is None:
        console.print("[red]Daemon not running. Start with: chimera serve[/red]")
        return
    
    if as_json:
        console.print(json.dumps(result, indent=2))
        return
    
    discoveries_list = result.get("discoveries", [])
    if not discoveries_list:
        console.print("[yellow]No discoveries found. Run correlation first: chimera correlate[/yellow]")
        return
    
    console.print(Panel.fit(f"[bold]💡 Discoveries ({len(discoveries_list)})[/bold]", border_style="yellow"))
    
    # Group by type
    by_type = {}
    for d in discoveries_list:
        dt = d.get("discovery_type", "unknown")
        if dt not in by_type:
            by_type[dt] = []
        by_type[dt].append(d)
    
    type_icons = {
        "expertise": "🎯",
        "relationship": "🔗",
        "workflow": "📁",
        "skill": "🛠️",
    }
    
    for dtype, items in by_type.items():
        icon = type_icons.get(dtype, "💡")
        console.print(f"\n{icon} [bold cyan]{dtype.upper()}[/bold cyan]")
        
        for d in items:
            conf = d.get("confidence", 0)
            title = d.get("title", "Untitled")
            desc = d.get("description", "")
            disc_id = d.get("id", "")
            status = d.get("status", "active")
            
            status_icon = {"active": "🟡", "confirmed": "✅", "dismissed": "❌"}.get(status, "❓")
            
            if conf >= 0.9:
                conf_color = "green bold"
            elif conf >= 0.7:
                conf_color = "green"
            else:
                conf_color = "yellow"
            
            console.print(f"  {status_icon} [{conf_color}][{conf:.0%}][/{conf_color}] {title}")
            console.print(f"     [dim]{desc}[/dim]")
            console.print(f"     [dim]ID: {disc_id}[/dim]")


@main.command()
@click.argument("discovery_id")
@click.option("--action", type=click.Choice(["confirm", "dismiss"]), required=True)
@click.option("--notes", help="Optional feedback notes")
def feedback(discovery_id: str, action: str, notes: str | None) -> None:
    """Provide feedback on a discovery."""
    result = api_request("POST", f"/api/v1/discoveries/{discovery_id}/feedback", json={
        "action": action,
        "notes": notes,
    })
    
    if result is None:
        console.print("[red]Daemon not running.[/red]")
        return
    
    if result.get("success"):
        icon = "✅" if action == "confirm" else "❌"
        console.print(f"{icon} Discovery {action}ed: {discovery_id}")
    else:
        console.print(f"[red]Failed: {result.get('error', 'Unknown error')}[/red]")


@main.command()
@click.option("--type", "entity_type", help="Filter by type (PERSON, ORG, TECH, etc)")
@click.option("--min-occurrences", default=2, help="Minimum occurrence count")
@click.option("--limit", default=50, help="Maximum results")
def entities(entity_type: str | None, min_occurrences: int, limit: int) -> None:
    """List consolidated entities."""
    params = f"min_occurrences={min_occurrences}&limit={limit}"
    if entity_type:
        params += f"&entity_type={entity_type}"
    
    result = api_request("GET", f"/api/v1/entities?{params}")
    
    if result is None:
        console.print("[red]Daemon not running.[/red]")
        return
    
    entities_list = result.get("entities", [])
    if not entities_list:
        console.print("[yellow]No entities found. Index some files first.[/yellow]")
        return
    
    console.print(Panel.fit(f"[bold]🏷️  Consolidated Entities ({len(entities_list)})[/bold]", border_style="cyan"))
    
    table = Table()
    table.add_column("Type", style="cyan")
    table.add_column("Value")
    table.add_column("Occurrences", justify="right")
    table.add_column("Files", justify="right")
    
    for e in entities_list:
        table.add_row(
            e.get("entity_type", ""),
            e.get("canonical_value", ""),
            str(e.get("occurrence_count", 0)),
            str(len(e.get("file_ids", []))),
        )
    
    console.print(table)


@main.command()
@click.option("--type", "pattern_type", help="Filter by type")
@click.option("--min-confidence", default=0.5, help="Minimum confidence")
def patterns(pattern_type: str | None, min_confidence: float) -> None:
    """List detected patterns."""
    params = f"min_confidence={min_confidence}"
    if pattern_type:
        params += f"&pattern_type={pattern_type}"
    
    result = api_request("GET", f"/api/v1/patterns?{params}")
    
    if result is None:
        console.print("[red]Daemon not running.[/red]")
        return
    
    patterns_list = result.get("patterns", [])
    if not patterns_list:
        console.print("[yellow]No patterns found. Run correlation first.[/yellow]")
        return
    
    console.print(Panel.fit(f"[bold]📊 Detected Patterns ({len(patterns_list)})[/bold]", border_style="magenta"))
    
    for p in patterns_list:
        conf = p.get("confidence", 0)
        console.print(f"\n[{'green' if conf >= 0.7 else 'yellow'}][{conf:.0%}][/] {p.get('title')}")
        console.print(f"   [dim]{p.get('description')}[/dim]")


@main.command()
@click.option("--now", is_flag=True, help="Run synchronously (wait for completion)")
def correlate(now: bool) -> None:
    """Run correlation analysis to detect patterns and surface discoveries."""
    console.print(f"{daemon_status_dot()} [bold]Correlation Analysis[/bold]\n")

    if now:
        # Synchronous with progress
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Running correlation...", total=None)

            result, error = api_request_with_spinner(
                "POST", "/api/v1/correlate/run",
                "Consolidating entities and detecting patterns..."
            )

            if error:
                print_error("Correlation failed", error)
                return

            progress.update(task, completed=True)

        if result and result.get("status") == "completed":
            r = result.get("result", {})
            stats = r.get("stats", {})
            timing = r.get("timing", {})

            print_success("Correlation complete")
            console.print()

            # Stats table
            table = Table(show_header=False, box=None, padding=(0, 2))
            table.add_column("Metric", style="cyan")
            table.add_column("Value", justify="right")

            table.add_row("Entities consolidated", f"{stats.get('entities_consolidated', 0):,}")
            table.add_row("Co-occurrence pairs", f"{stats.get('co_occurrence_pairs', 0):,}")
            table.add_row("Patterns detected", str(stats.get('patterns_detected', 0)))
            table.add_row("Discoveries surfaced", f"[bold yellow]{stats.get('discoveries_surfaced', 0)}[/bold yellow]")
            table.add_row("Time elapsed", f"{timing.get('total_time', 0):.2f}s")

            console.print(table)

            if stats.get('discoveries_surfaced', 0) > 0:
                console.print(f"\n[dim]View with:[/dim] [cyan]chimera discoveries[/cyan]")
        else:
            print_error("Correlation returned unexpected status", str(result))
    else:
        # Async queue
        result, error = api_request_with_spinner(
            "POST", "/api/v1/correlate",
            "Queueing correlation job..."
        )

        if error:
            print_error("Failed to queue correlation", error)
            return

        if result and result.get("status") == "queued":
            print_success(f"Correlation queued")
            console.print(f"  [dim]Job ID: {result.get('job_id')}[/dim]")
            console.print(f"\n[dim]Monitor with:[/dim] [cyan]chimera jobs[/cyan]")
        else:
            print_error("Unexpected response", str(result))


@main.command()
@click.option("--files", is_flag=True, help="Excavate files only")
@click.option("--fae", is_flag=True, help="Excavate AI exports only")
@click.option("--correlate", "do_correlate", is_flag=True, help="Run correlation after")
@click.argument("paths", nargs=-1)
def excavate(files: bool, fae: bool, do_correlate: bool, paths: tuple) -> None:
    """Trigger cognitive archaeology excavation."""
    if not files and not fae:
        files = True
        fae = True
        do_correlate = True

    console.print(f"{daemon_status_dot()} [bold]Excavation[/bold]\n")

    # Show scope
    scope_items = []
    if files:
        scope_items.append("[green]✓[/green] Files")
    if fae:
        scope_items.append("[green]✓[/green] FAE exports")
    if do_correlate:
        scope_items.append("[green]✓[/green] Correlation")
    if paths:
        scope_items.append(f"[cyan]→[/cyan] {len(paths)} path(s)")

    for item in scope_items:
        console.print(f"  {item}")
    console.print()

    result, error = api_request_with_spinner(
        "POST", "/api/v1/excavate",
        "Queueing excavation job...",
        json={
            "files": files,
            "fae": fae,
            "correlate": do_correlate,
            "paths": list(paths) if paths else None,
        }
    )

    if error:
        print_error("Failed to start excavation", error)
        return

    if result and result.get("status") == "queued":
        print_success("Excavation started")
        console.print(f"  [dim]Job ID: {result.get('job_id')}[/dim]")
        console.print(f"\n[dim]Monitor progress:[/dim] [cyan]chimera dashboard[/cyan]")
        console.print(f"[dim]Check jobs:[/dim] [cyan]chimera jobs[/cyan]")
    else:
        print_error("Unexpected response", str(result))


@main.command(name="fae")
@click.argument("path", required=False)
@click.option("--provider", type=click.Choice(["auto", "claude", "chatgpt", "gemini", "grok"]), default="auto")
@click.option("--correlate/--no-correlate", default=True)
def fae_command(path: str | None, provider: str, correlate: bool) -> None:
    """Process AI conversation exports (Full Archaeology Excavation)."""
    console.print("[bold]🤖 FAE — Full Archaeology Excavation[/bold]")
    console.print(f"  Provider: {provider}")
    if path:
        console.print(f"  Path: {path}")
    
    result = api_request("POST", "/api/v1/fae", json={
        "path": path or "default",
        "provider": provider,
        "correlate": correlate,
    })
    
    if result is None:
        console.print("\n[red]Daemon not running.[/red]")
        return
    
    if result.get("status") == "queued":
        console.print(f"\n[green]✅ FAE queued. Job ID: {result.get('job_id')}[/green]")
    else:
        console.print(f"\n[red]Error: {result.get('error', 'Unknown error')}[/red]")


@main.group(invoke_without_command=True)
@click.pass_context
def config(ctx) -> None:
    """Configuration management.

    Without subcommand, shows current configuration.
    """
    if ctx.invoked_subcommand is None:
        # Default behavior: show config
        ctx.invoke(config_show)


@config.command("show")
def config_show() -> None:
    """Show current configuration."""
    cfg = load_config()

    console.print(Panel.fit("[bold]CHIMERA Configuration[/bold]", border_style="cyan"))

    console.print(f"\n[cyan]Version:[/cyan] {cfg.version}")

    console.print(f"\n[cyan]Sources ({len(cfg.sources)}):[/cyan]")
    for i, s in enumerate(cfg.sources):
        status = "✅" if s.enabled else "❌"
        depth = f" (depth: {s.max_depth})" if s.max_depth else ""
        console.print(f"  {status} [{i}] {s.path} ({s.priority}){depth}")

    console.print(f"\n[cyan]Vision:[/cyan]")
    console.print(f"  Provider: {cfg.vision.provider}")
    console.print(f"  Fallback: {', '.join(cfg.vision.fallback_providers)}")
    console.print(f"  Enabled: {'✅' if cfg.vision.enabled else '❌'}")

    console.print(f"\n[cyan]API Keys:[/cyan]")
    for provider in ["openai", "anthropic", "google"]:
        key = cfg.api_keys.get_key(provider)
        if key:
            masked = key[:8] + "..." + key[-4:] if len(key) > 16 else "***"
            console.print(f"  {provider}: [green]✓[/green] {masked}")
        else:
            console.print(f"  {provider}: [dim]not set[/dim]")

    console.print(f"\n[cyan]FAE:[/cyan]")
    console.print(f"  Enabled: {'✅' if cfg.fae.enabled else '❌'}")
    if cfg.fae.watch_paths:
        console.print(f"  Watch: {', '.join(cfg.fae.watch_paths)}")

    console.print(f"\n[cyan]API:[/cyan] {cfg.api.host}:{cfg.api.port}")

    console.print(f"\n[dim]Config file: {get_config_path()}[/dim]")


@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key: str, value: str) -> None:
    """Set a configuration value.

    Examples:
        chimera config set vision.provider claude
        chimera config set sources.0.max_depth 5
        chimera config set api_keys.openai sk-xxx
    """
    cfg = load_config()

    try:
        set_nested_value(cfg, key, value)
        save_config(cfg)
        print_success(f"Set {key} = {value}")
    except KeyError as e:
        print_error(f"Invalid config key: {key}", str(e))
    except ValueError as e:
        print_error(f"Invalid value for {key}", str(e))


@config.command("get")
@click.argument("key")
def config_get(key: str) -> None:
    """Get a configuration value.

    Examples:
        chimera config get vision.provider
        chimera config get sources.0.path
    """
    cfg = load_config()
    value = get_nested_value(cfg, key)

    if value is None:
        print_error(f"Key not found: {key}")
    else:
        console.print(f"{key} = {value}")


@config.command("test-api")
@click.option("--provider", default="all", help="Provider to test (openai, anthropic, google, all)")
def config_test_api(provider: str) -> None:
    """Test API key configuration.

    Example:
        chimera config test-api
        chimera config test-api --provider openai
    """
    results = test_api_keys(provider)

    console.print(Panel.fit("[bold]API Key Status[/bold]", border_style="cyan"))

    for name, configured in results.items():
        if configured:
            console.print(f"  [green]✓[/green] {name}")
        else:
            console.print(f"  [red]✗[/red] {name} [dim](not configured)[/dim]")


@config.command("edit")
def config_edit() -> None:
    """Open config file in default editor."""
    config_path = get_config_path()

    if not config_path.exists():
        # Create default config first
        cfg = get_default_config()
        save_config(cfg)
        print_info(f"Created default config: {config_path}")

    click.edit(filename=str(config_path))


@main.command()
def init() -> None:
    """Initialize CHIMERA configuration."""
    console.print("[bold]Initializing CHIMERA...[/bold]")
    
    config_dir = ensure_config_dir()
    console.print(f"  ✅ {config_dir}")
    
    from chimera.config import DEFAULT_CONFIG_FILE
    
    if DEFAULT_CONFIG_FILE.exists():
        console.print(f"  [dim]Config exists: {DEFAULT_CONFIG_FILE}[/dim]")
    else:
        cfg = get_default_config()
        save_config(cfg)
        console.print(f"  ✅ Created: {DEFAULT_CONFIG_FILE}")
    
    console.print("\n[green]✅ CHIMERA initialized.[/green]")
    console.print("\nNext: [cyan]chimera serve[/cyan]")


@main.command()
def jobs() -> None:
    """Show job queue statistics."""
    result = api_request("GET", "/api/v1/jobs")
    
    if result is None:
        console.print("[red]Daemon not running.[/red]")
        return
    
    console.print(Panel.fit("[bold]Job Queue[/bold]", border_style="blue"))
    console.print(f"Pending: {result.get('pending', 0)}")
    
    stats = result.get("stats", {})
    if stats.get("by_status"):
        console.print("\n[cyan]By Status:[/cyan]")
        for status, count in stats["by_status"].items():
            console.print(f"  {status}: {count}")


@main.command()
def logs() -> None:
    """Show recent daemon logs."""
    from chimera.config import DEFAULT_CONFIG_DIR
    
    log_file = DEFAULT_CONFIG_DIR / "logs" / "chimerad.log"
    
    if not log_file.exists():
        console.print("[yellow]No log file found.[/yellow]")
        return
    
    with open(log_file) as f:
        lines = f.readlines()[-50:]
    
    console.print("[bold]Recent Logs[/bold]")
    for line in lines:
        console.print(line.rstrip())


# ============ Sprint 4: Graph Sync Commands ============

@main.command(name="graph-export")
@click.option("--output", "-o", default="discoveries.yaml", help="Output file")
@click.option("--format", "fmt", type=click.Choice(["yaml", "json"]), default="yaml")
def graph_export(output: str, fmt: str) -> None:
    """Export discoveries as SIF pointer graph nodes."""
    result = api_request("GET", "/api/v1/graph/export")
    
    if result is None:
        console.print("[red]Daemon not running.[/red]")
        return
    
    nodes = result.get("nodes", [])
    
    if not nodes:
        console.print("[yellow]No discoveries to export. Run correlation first.[/yellow]")
        return
    
    output_path = Path(output)
    
    if fmt == "yaml":
        import yaml
        with open(output_path, "w") as f:
            yaml.dump({"discoveries": nodes}, f, default_flow_style=False)
    else:
        with open(output_path, "w") as f:
            json.dump({"discoveries": nodes}, f, indent=2)
    
    console.print(f"[green]✅ Exported {len(nodes)} discoveries to {output_path}[/green]")


@main.command(name="graph-sync")
@click.option("--repo", default="Dshamir/sif-knowledge-base", help="GitHub repo")
@click.option("--path", default="chimera/discoveries.yaml", help="Path in repo")
@click.option("--dry-run", is_flag=True, help="Show what would be synced")
def graph_sync(repo: str, path: str, dry_run: bool) -> None:
    """Sync discoveries to SIF knowledge base on GitHub."""
    result = api_request("POST", "/api/v1/graph/sync", json={
        "repo": repo,
        "path": path,
        "dry_run": dry_run,
    })
    
    if result is None:
        console.print("[red]Daemon not running.[/red]")
        return
    
    if dry_run:
        console.print("[bold]Dry Run - Would sync:[/bold]")
        nodes = result.get("nodes", [])
        for n in nodes[:10]:
            console.print(f"  - {n.get('label', 'unknown')}")
        if len(nodes) > 10:
            console.print(f"  ... and {len(nodes) - 10} more")
    elif result.get("success"):
        console.print(f"[green]✅ Synced {result.get('count', 0)} discoveries to {repo}[/green]")
    else:
        console.print(f"[red]Sync failed: {result.get('error', 'Unknown error')}[/red]")


# ============ Sprint 4: Claude Integration ============

@main.command()
@click.argument("question")
@click.option("--context", "-c", default=5, help="Number of context chunks")
def ask(question: str, context: int) -> None:
    """Ask a question using CHIMERA context (for Claude integration)."""
    # Get relevant context
    result = api_request("GET", f"/api/v1/query?q={question}&limit={context}")
    
    if result is None:
        console.print("[red]Daemon not running.[/red]")
        return
    
    chunks = result.get("results", [])
    discoveries = api_request("GET", f"/api/v1/discoveries?limit=5")
    discoveries_list = discoveries.get("discoveries", []) if discoveries else []
    
    # Build context block for Claude
    console.print(Panel.fit("[bold]Context for Claude[/bold]", border_style="magenta"))
    
    context_text = f"""<chimera_context>
<question>{question}</question>

<relevant_content>
"""
    for i, chunk in enumerate(chunks, 1):
        context_text += f"""<chunk index="{i}" similarity="{chunk.get('similarity', 0):.2f}" source="{chunk.get('file_path', '')}">
{chunk.get('content', '')}
</chunk>

"""
    
    if discoveries_list:
        context_text += """</relevant_content>

<discoveries>
"""
        for d in discoveries_list:
            context_text += f"""<discovery type="{d.get('discovery_type')}" confidence="{d.get('confidence', 0):.2f}">
{d.get('title')}: {d.get('description', '')}
</discovery>

"""
        context_text += "</discoveries>\n"
    else:
        context_text += "</relevant_content>\n"
    
    context_text += "</chimera_context>"
    
    console.print(Syntax(context_text, "xml", theme="monokai"))
    
    console.print("\n[dim]Copy the above context block when asking Claude.[/dim]")


@main.command()
def summary() -> None:
    """Generate a summary of indexed knowledge (for Claude context)."""
    # Get stats
    status = api_request("GET", "/api/v1/status")
    correlation = api_request("GET", "/api/v1/correlation/stats")
    discoveries = api_request("GET", "/api/v1/discoveries?limit=10")
    entities = api_request("GET", "/api/v1/entities?limit=20")
    
    if status is None:
        console.print("[red]Daemon not running.[/red]")
        return
    
    console.print(Panel.fit("[bold]🧠 CHIMERA Knowledge Summary[/bold]", border_style="green"))
    
    # Stats
    catalog = status.get("catalog", {})
    console.print(f"\n[cyan]Index Stats:[/cyan]")
    console.print(f"  Files: {catalog.get('total_files', 0)}")
    console.print(f"  Chunks: {catalog.get('total_chunks', 0)}")
    console.print(f"  Entities: {catalog.get('total_entities', 0)}")
    
    # Top entities
    if entities and entities.get("entities"):
        console.print(f"\n[cyan]Top Entities:[/cyan]")
        for e in entities["entities"][:10]:
            console.print(f"  [{e.get('entity_type')}] {e.get('canonical_value')} ({e.get('occurrence_count')}x)")
    
    # Discoveries
    if discoveries and discoveries.get("discoveries"):
        console.print(f"\n[cyan]Active Discoveries:[/cyan]")
        for d in discoveries["discoveries"][:5]:
            console.print(f"  [{d.get('confidence', 0):.0%}] {d.get('title')}")
    
    # Correlation stats
    if correlation:
        console.print(f"\n[cyan]Correlation:[/cyan]")
        console.print(f"  Patterns: {correlation.get('patterns', {}).get('total', 0)}")
        console.print(f"  Discoveries: {correlation.get('discoveries', {}).get('total', 0)}")


if __name__ == "__main__":
    main()
