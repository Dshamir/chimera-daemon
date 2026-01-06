"""CHIMERA Unified Interactive Shell.

One terminal. One command. Everything integrated.
"""

import asyncio
import os
import sys
import signal
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
import json

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.markdown import Markdown
    from rich.syntax import Syntax
    from rich.live import Live
    from rich.spinner import Spinner
    from rich.prompt import Prompt, Confirm
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.completion import WordCompleter
except ImportError:
    print("Installing required packages...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "prompt_toolkit", "-q"])
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.markdown import Markdown
    from rich.syntax import Syntax
    from rich.live import Live
    from rich.spinner import Spinner
    from rich.prompt import Prompt, Confirm
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.completion import WordCompleter

from chimera import __version__
from chimera.config import load_config, save_config, ensure_config_dir, DEFAULT_CONFIG_DIR

console = Console()

# Session logging
SESSION_LOG_DIR = DEFAULT_CONFIG_DIR / "sessions"
SESSION_LOG_DIR.mkdir(parents=True, exist_ok=True)


class SessionLogger:
    """Logs all shell commands and outputs."""
    
    def __init__(self):
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = SESSION_LOG_DIR / f"session_{self.session_id}.jsonl"
        self.start_time = datetime.now()
    
    def log(self, event_type: str, data: dict):
        """Log an event."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event_type,
            **data
        }
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
    
    def log_command(self, command: str):
        self.log("command", {"command": command})
    
    def log_result(self, command: str, success: bool, output: str = ""):
        self.log("result", {"command": command, "success": success, "output": output[:500]})
    
    def log_error(self, command: str, error: str):
        self.log("error", {"command": command, "error": error})


class DaemonManager:
    """Manages the CHIMERA daemon process."""
    
    def __init__(self):
        self.process = None
        self.thread = None
        self.running = False
        self._loop = None
    
    def start(self, dev_mode: bool = True) -> bool:
        """Start the daemon in background."""
        if self.running:
            return True
        
        try:
            from chimera.daemon import ChimeraDaemon
            
            self._loop = asyncio.new_event_loop()
            self.daemon = ChimeraDaemon(dev_mode=dev_mode)
            
            def run_daemon():
                asyncio.set_event_loop(self._loop)
                try:
                    self._loop.run_until_complete(self.daemon.start())
                except Exception as e:
                    console.print(f"[red]Daemon error: {e}[/red]")
            
            self.thread = threading.Thread(target=run_daemon, daemon=True)
            self.thread.start()
            self.running = True
            
            # Wait for startup
            time.sleep(2)
            return self.health_check()
            
        except Exception as e:
            console.print(f"[red]Failed to start daemon: {e}[/red]")
            return False
    
    def stop(self):
        """Stop the daemon."""
        if self._loop and self.daemon:
            try:
                self._loop.call_soon_threadsafe(self._loop.stop)
            except:
                pass
        self.running = False
    
    def health_check(self) -> bool:
        """Check if daemon is healthy."""
        try:
            import httpx
            r = httpx.get("http://127.0.0.1:7777/api/v1/health", timeout=2)
            return r.status_code == 200
        except:
            return False
    
    def get_status(self) -> dict:
        """Get daemon status."""
        try:
            import httpx
            r = httpx.get("http://127.0.0.1:7777/api/v1/status", timeout=5)
            return r.json()
        except:
            return {}


class ChimeraShell:
    """Unified CHIMERA Interactive Shell."""
    
    def __init__(self):
        self.daemon = DaemonManager()
        self.logger = SessionLogger()
        self.running = True
        
        # Command history
        history_file = DEFAULT_CONFIG_DIR / "shell_history"
        self.session = PromptSession(
            history=FileHistory(str(history_file)),
            auto_suggest=AutoSuggestFromHistory(),
        )
        
        # Commands
        self.commands = {
            # Daemon
            "/start": self.cmd_start,
            "/stop": self.cmd_stop,
            "/status": self.cmd_status,
            "/health": self.cmd_health,
            
            # Search & Query
            "/search": self.cmd_search,
            "/query": self.cmd_search,  # alias
            "/q": self.cmd_search,  # short alias
            
            # Indexing
            "/index": self.cmd_index,
            "/excavate": self.cmd_excavate,
            "/fae": self.cmd_fae,
            
            # Intelligence
            "/correlate": self.cmd_correlate,
            "/discoveries": self.cmd_discoveries,
            "/entities": self.cmd_entities,
            "/patterns": self.cmd_patterns,
            
            # Configuration
            "/config": self.cmd_config,
            "/sources": self.cmd_sources,
            "/add-source": self.cmd_add_source,
            
            # Logs & Analytics
            "/logs": self.cmd_logs,
            "/sessions": self.cmd_sessions,
            "/stats": self.cmd_stats,
            
            # Utilities
            "/help": self.cmd_help,
            "/?": self.cmd_help,
            "/clear": self.cmd_clear,
            "/exit": self.cmd_exit,
            "/quit": self.cmd_exit,
        }
        
        self.completer = WordCompleter(
            list(self.commands.keys()) + ["/help"],
            ignore_case=True
        )
    
    def print_banner(self):
        """Print welcome banner."""
        banner = """
   ██████╗██╗  ██╗██╗███╗   ███╗███████╗██████╗  █████╗ 
  ██╔════╝██║  ██║██║████╗ ████║██╔════╝██╔══██╗██╔══██╗
  ██║     ███████║██║██╔████╔██║█████╗  ██████╔╝███████║
  ██║     ██╔══██║██║██║╚██╔╝██║██╔══╝  ██╔══██╗██╔══██║
  ╚██████╗██║  ██║██║██║ ╚═╝ ██║███████╗██║  ██║██║  ██║
   ╚═════╝╚═╝  ╚═╝╚═╝╚═╝     ╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝
        """
        console.print(banner, style="bold cyan")
        console.print(f"  [dim]Cognitive History Integration & Memory Extraction[/dim]")
        console.print(f"  [dim]Version {__version__} | Type /help for commands[/dim]\n")
    
    def print_status_bar(self):
        """Print current status."""
        status = self.daemon.get_status()
        if status.get("running"):
            stats = status.get("stats", {})
            catalog = status.get("catalog", {})
            console.print(
                f"[green]●[/green] Daemon running | "
                f"📁 {catalog.get('total_files', stats.get('files_indexed', 0))} files | "
                f"🧩 {catalog.get('total_chunks', 0)} chunks | "
                f"🏷️ {catalog.get('total_entities', 0)} entities",
                style="dim"
            )
        else:
            console.print("[red]●[/red] Daemon stopped | Type [cyan]/start[/cyan] to begin", style="dim")
    
    async def run(self):
        """Main shell loop."""
        self.print_banner()
        
        # Auto-start daemon
        console.print("[yellow]Starting CHIMERA daemon...[/yellow]")
        if self.daemon.health_check():
            console.print("[green]✓ Daemon already running[/green]")
            self.daemon.running = True
        else:
            # Try to start via API server directly
            console.print("[dim]Initializing...[/dim]")
            self._start_api_server()
        
        console.print()
        self.print_status_bar()
        console.print()
        
        while self.running:
            try:
                # Get input
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.session.prompt(
                        "chimera> ",
                        completer=self.completer,
                    )
                )
                
                user_input = user_input.strip()
                if not user_input:
                    continue
                
                self.logger.log_command(user_input)
                
                # Parse command
                if user_input.startswith("/"):
                    parts = user_input.split(maxsplit=1)
                    cmd = parts[0].lower()
                    args = parts[1] if len(parts) > 1 else ""
                    
                    if cmd in self.commands:
                        try:
                            await self.commands[cmd](args)
                            self.logger.log_result(cmd, True)
                        except Exception as e:
                            console.print(f"[red]Error: {e}[/red]")
                            self.logger.log_error(cmd, str(e))
                    else:
                        console.print(f"[yellow]Unknown command: {cmd}. Type /help for commands.[/yellow]")
                else:
                    # Default: treat as search query
                    await self.cmd_search(user_input)
                
                console.print()
                
            except KeyboardInterrupt:
                console.print("\n[dim]Use /exit to quit[/dim]")
            except EOFError:
                break
        
        # Cleanup
        self.daemon.stop()
        console.print("\n[cyan]CHIMERA session ended. Goodbye![/cyan]")
    
    def _start_api_server(self):
        """Start API server in background thread."""
        import subprocess
        self._server_process = subprocess.Popen(
            [sys.executable, "-m", "chimera.cli", "serve", "--dev"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(3)
        if self.daemon.health_check():
            console.print("[green]✓ Daemon started[/green]")
            self.daemon.running = True
        else:
            console.print("[yellow]⚠ Daemon may not be fully ready[/yellow]")
    
    # ============ COMMANDS ============
    
    async def cmd_help(self, args: str):
        """Show help."""
        table = Table(title="CHIMERA Commands", show_header=True)
        table.add_column("Command", style="cyan")
        table.add_column("Description")
        
        help_text = [
            ("/start", "Start the daemon"),
            ("/stop", "Stop the daemon"),
            ("/status", "Show daemon status"),
            ("/health", "Check daemon health"),
            ("", ""),
            ("/search <query>", "Search indexed content (or just type query)"),
            ("/q <query>", "Short alias for search"),
            ("/index <path>", "Index a specific file"),
            ("/excavate", "Full excavation (all sources)"),
            ("/fae <path>", "Process AI conversation exports"),
            ("", ""),
            ("/correlate", "Run correlation analysis"),
            ("/discoveries", "Show discovered patterns"),
            ("/entities", "List extracted entities"),
            ("/patterns", "Show detected patterns"),
            ("", ""),
            ("/config", "Show configuration"),
            ("/sources", "List watched sources"),
            ("/add-source <path>", "Add a new source directory"),
            ("", ""),
            ("/logs", "Show recent logs"),
            ("/sessions", "List past sessions"),
            ("/stats", "Show analytics"),
            ("", ""),
            ("/clear", "Clear screen"),
            ("/exit", "Exit CHIMERA"),
        ]
        
        for cmd, desc in help_text:
            if cmd:
                table.add_row(cmd, desc)
            else:
                table.add_row("", "")
        
        console.print(table)
        console.print("\n[dim]Tip: Just type a query directly to search![/dim]")
    
    async def cmd_start(self, args: str):
        """Start daemon."""
        if self.daemon.health_check():
            console.print("[green]Daemon already running[/green]")
            return
        
        console.print("[yellow]Starting daemon...[/yellow]")
        self._start_api_server()
    
    async def cmd_stop(self, args: str):
        """Stop daemon."""
        if hasattr(self, '_server_process'):
            self._server_process.terminate()
            console.print("[yellow]Daemon stopped[/yellow]")
        self.daemon.stop()
    
    async def cmd_status(self, args: str):
        """Show status."""
        status = self.daemon.get_status()
        
        if not status:
            console.print("[red]Daemon not responding[/red]")
            return
        
        console.print(Panel.fit("[bold green]CHIMERA Status[/bold green]", border_style="green"))
        
        table = Table(show_header=False, box=None)
        table.add_column("Key", style="cyan")
        table.add_column("Value")
        
        table.add_row("Version", status.get("version", "?"))
        table.add_row("Running", "✅" if status.get("running") else "❌")
        
        uptime = status.get('uptime_seconds', 0)
        if uptime > 3600:
            uptime_str = f"{uptime/3600:.1f}h"
        elif uptime > 60:
            uptime_str = f"{uptime/60:.1f}m"
        else:
            uptime_str = f"{uptime:.0f}s"
        table.add_row("Uptime", uptime_str)
        
        stats = status.get("stats", {})
        catalog = status.get("catalog", {})
        
        table.add_row("", "")
        table.add_row("📁 Files", str(catalog.get('total_files', stats.get('files_indexed', 0))))
        table.add_row("🧩 Chunks", str(catalog.get('total_chunks', 0)))
        table.add_row("🏷️ Entities", str(catalog.get('total_entities', 0)))
        table.add_row("💡 Discoveries", str(catalog.get('active_discoveries', 0)))
        
        console.print(table)
    
    async def cmd_health(self, args: str):
        """Check health."""
        if self.daemon.health_check():
            console.print("[green]✓ Daemon is healthy[/green]")
        else:
            console.print("[red]✗ Daemon not responding[/red]")
    
    async def cmd_search(self, args: str):
        """Search indexed content."""
        if not args:
            console.print("[yellow]Usage: /search <query>[/yellow]")
            return
        
        console.print(f"[dim]Searching: {args}[/dim]")
        
        try:
            from chimera.storage.vectors import VectorDB
            from chimera.extractors.embeddings import get_embedding_generator
            
            embedder = get_embedding_generator()
            vectors = VectorDB()
            
            query_embedding = embedder.embed(args)
            results = vectors.query("documents", query_embedding, n_results=5)
            
            if results and results.get("ids") and results["ids"][0]:
                console.print(Panel.fit(f"[bold]Results for: {args}[/bold]", border_style="blue"))
                
                for i, (doc_id, doc, meta, dist) in enumerate(zip(
                    results["ids"][0],
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0]
                ), 1):
                    similarity = 1 - dist
                    color = "green" if similarity > 0.5 else "yellow" if similarity > 0.3 else "dim"
                    
                    file_path = meta.get("file_path", "unknown")
                    file_name = Path(file_path).name
                    
                    console.print(f"\n[{color}]{i}. [{similarity:.0%}][/{color}] [cyan]{file_name}[/cyan]")
                    console.print(f"   [dim]{file_path}[/dim]")
                    console.print(f"   {doc[:150]}..." if len(doc) > 150 else f"   {doc}")
            else:
                console.print("[yellow]No results found[/yellow]")
                
        except Exception as e:
            console.print(f"[red]Search error: {e}[/red]")
    
    async def cmd_index(self, args: str):
        """Index a specific file."""
        if not args:
            console.print("[yellow]Usage: /index <file_path>[/yellow]")
            return
        
        file_path = Path(args.strip('"').strip("'"))
        
        if not file_path.exists():
            console.print(f"[red]File not found: {file_path}[/red]")
            return
        
        console.print(f"[yellow]Indexing: {file_path}[/yellow]")
        
        try:
            from chimera.extractors.pipeline import ExtractionPipeline
            
            pipeline = ExtractionPipeline()
            result = await pipeline.process_file(file_path)
            
            if result.success:
                console.print(f"[green]✓ Indexed: {result.chunk_count} chunks, {result.entity_count} entities[/green]")
            else:
                console.print(f"[red]✗ Failed: {result.error}[/red]")
                
        except Exception as e:
            console.print(f"[red]Index error: {e}[/red]")
    
    async def cmd_excavate(self, args: str):
        """Run full excavation."""
        console.print("[yellow]⛏️ Starting excavation...[/yellow]")
        
        try:
            import httpx
            r = httpx.post("http://127.0.0.1:7777/api/v1/excavate", json={
                "files": True,
                "fae": True,
                "correlate": True,
            }, timeout=10)
            result = r.json()
            
            if result.get("status") == "queued":
                console.print(f"[green]✓ Excavation queued: {result.get('job_id')}[/green]")
            else:
                console.print(f"[red]Error: {result.get('error')}[/red]")
        except Exception as e:
            console.print(f"[red]Excavation error: {e}[/red]")
    
    async def cmd_fae(self, args: str):
        """Process AI conversation exports."""
        path = args.strip('"').strip("'") if args else None
        
        console.print("[yellow]🤖 Processing AI exports...[/yellow]")
        
        try:
            import httpx
            r = httpx.post("http://127.0.0.1:7777/api/v1/fae", json={
                "path": path or "default",
                "provider": "auto",
                "correlate": True,
            }, timeout=10)
            result = r.json()
            
            if result.get("status") == "queued":
                console.print(f"[green]✓ FAE queued: {result.get('job_id')}[/green]")
            else:
                console.print(f"[red]Error: {result.get('error')}[/red]")
        except Exception as e:
            console.print(f"[red]FAE error: {e}[/red]")
    
    async def cmd_correlate(self, args: str):
        """Run correlation."""
        console.print("[yellow]🔗 Running correlation...[/yellow]")
        
        try:
            import httpx
            r = httpx.post("http://127.0.0.1:7777/api/v1/correlate/run", timeout=60)
            result = r.json()
            
            if result.get("status") == "completed":
                res = result.get("result", {})
                stats = res.get("stats", {})
                console.print(f"[green]✓ Correlation complete[/green]")
                console.print(f"  Entities: {stats.get('entities_consolidated', 0)}")
                console.print(f"  Patterns: {stats.get('patterns_detected', 0)}")
                console.print(f"  Discoveries: {stats.get('discoveries_surfaced', 0)}")
            else:
                console.print(f"[red]Error: {result.get('error')}[/red]")
        except Exception as e:
            console.print(f"[red]Correlation error: {e}[/red]")
    
    async def cmd_discoveries(self, args: str):
        """Show discoveries."""
        try:
            import httpx
            r = httpx.get("http://127.0.0.1:7777/api/v1/discoveries?min_confidence=0.1", timeout=10)
            result = r.json()
            
            discoveries = result.get("discoveries", [])
            if discoveries:
                console.print(Panel.fit(f"[bold]💡 Discoveries ({len(discoveries)})[/bold]", border_style="yellow"))
                for d in discoveries:
                    conf = d.get("confidence", 0)
                    console.print(f"  [{conf:.0%}] {d.get('title')}")
                    console.print(f"      [dim]{d.get('description')}[/dim]")
            else:
                # Show patterns instead
                await self.cmd_patterns("")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
    
    async def cmd_entities(self, args: str):
        """List entities."""
        try:
            import httpx
            r = httpx.get("http://127.0.0.1:7777/api/v1/entities?limit=30", timeout=10)
            result = r.json()
            
            entities = result.get("entities", [])
            if entities:
                table = Table(title=f"🏷️ Entities ({len(entities)})")
                table.add_column("Type", style="cyan")
                table.add_column("Value")
                table.add_column("Count", justify="right")
                
                for e in entities[:20]:
                    table.add_row(
                        e.get("entity_type", ""),
                        e.get("canonical_value", "")[:30],
                        str(e.get("occurrence_count", 0))
                    )
                
                console.print(table)
            else:
                console.print("[yellow]No entities found. Index some files first.[/yellow]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
    
    async def cmd_patterns(self, args: str):
        """Show patterns."""
        try:
            import httpx
            r = httpx.get("http://127.0.0.1:7777/api/v1/patterns?min_confidence=0.1", timeout=10)
            result = r.json()
            
            patterns = result.get("patterns", [])
            if patterns:
                console.print(Panel.fit(f"[bold]📊 Patterns ({len(patterns)})[/bold]", border_style="magenta"))
                for p in patterns:
                    conf = p.get("confidence", 0)
                    color = "green" if conf > 0.5 else "yellow"
                    console.print(f"  [{color}][{conf:.0%}][/{color}] {p.get('title')}")
                    console.print(f"      [dim]{p.get('description')}[/dim]")
            else:
                console.print("[yellow]No patterns found. Run /correlate first.[/yellow]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
    
    async def cmd_config(self, args: str):
        """Show config."""
        cfg = load_config()
        
        console.print(Panel.fit("[bold]Configuration[/bold]", border_style="cyan"))
        console.print(f"\n[cyan]Version:[/cyan] {cfg.version}")
        console.print(f"[cyan]Config Dir:[/cyan] {DEFAULT_CONFIG_DIR}")
        
        console.print(f"\n[cyan]Sources ({len(cfg.sources)}):[/cyan]")
        for s in cfg.sources:
            status = "✅" if s.enabled else "❌"
            console.print(f"  {status} {s.path}")
        
        console.print(f"\n[cyan]FAE:[/cyan] {'Enabled' if cfg.fae.enabled else 'Disabled'}")
        console.print(f"[cyan]API:[/cyan] {cfg.api.host}:{cfg.api.port}")
    
    async def cmd_sources(self, args: str):
        """List sources."""
        cfg = load_config()
        
        table = Table(title="Watched Sources")
        table.add_column("Status")
        table.add_column("Path")
        table.add_column("Priority")
        
        for s in cfg.sources:
            table.add_row(
                "✅" if s.enabled else "❌",
                s.path,
                s.priority
            )
        
        console.print(table)
    
    async def cmd_add_source(self, args: str):
        """Add a source."""
        if not args:
            console.print("[yellow]Usage: /add-source <path>[/yellow]")
            return
        
        path = args.strip('"').strip("'")
        
        if not Path(path).exists():
            console.print(f"[red]Path not found: {path}[/red]")
            return
        
        cfg = load_config()
        from chimera.config import SourceConfig
        cfg.sources.append(SourceConfig(path=path, enabled=True, priority="medium"))
        save_config(cfg)
        
        console.print(f"[green]✓ Added source: {path}[/green]")
        console.print("[dim]Restart daemon to apply changes[/dim]")
    
    async def cmd_logs(self, args: str):
        """Show logs."""
        log_file = DEFAULT_CONFIG_DIR / "logs" / "chimerad.log"
        
        if not log_file.exists():
            console.print("[yellow]No log file found[/yellow]")
            return
        
        with open(log_file) as f:
            lines = f.readlines()[-30:]
        
        console.print(Panel.fit("[bold]Recent Logs[/bold]", border_style="blue"))
        for line in lines:
            console.print(line.rstrip())
    
    async def cmd_sessions(self, args: str):
        """List sessions."""
        sessions = sorted(SESSION_LOG_DIR.glob("session_*.jsonl"), reverse=True)
        
        if not sessions:
            console.print("[yellow]No sessions found[/yellow]")
            return
        
        table = Table(title="Past Sessions")
        table.add_column("Date")
        table.add_column("Session ID")
        table.add_column("Commands")
        
        for s in sessions[:10]:
            # Count commands
            with open(s) as f:
                cmd_count = sum(1 for line in f if '"event": "command"' in line)
            
            session_id = s.stem.replace("session_", "")
            date = f"{session_id[:4]}-{session_id[4:6]}-{session_id[6:8]} {session_id[9:11]}:{session_id[11:13]}"
            
            table.add_row(date, session_id, str(cmd_count))
        
        console.print(table)
    
    async def cmd_stats(self, args: str):
        """Show analytics."""
        # Count total sessions
        sessions = list(SESSION_LOG_DIR.glob("session_*.jsonl"))
        
        # Count total commands across all sessions
        total_cmds = 0
        cmd_counts = {}
        for s in sessions:
            with open(s) as f:
                for line in f:
                    if '"event": "command"' in line:
                        total_cmds += 1
                        try:
                            data = json.loads(line)
                            cmd = data.get("command", "").split()[0]
                            cmd_counts[cmd] = cmd_counts.get(cmd, 0) + 1
                        except:
                            pass
        
        console.print(Panel.fit("[bold]📊 Analytics[/bold]", border_style="green"))
        console.print(f"\n[cyan]Total Sessions:[/cyan] {len(sessions)}")
        console.print(f"[cyan]Total Commands:[/cyan] {total_cmds}")
        console.print(f"[cyan]Current Session:[/cyan] {self.logger.session_id}")
        
        if cmd_counts:
            console.print(f"\n[cyan]Top Commands:[/cyan]")
            for cmd, count in sorted(cmd_counts.items(), key=lambda x: -x[1])[:5]:
                console.print(f"  {cmd}: {count}")
    
    async def cmd_clear(self, args: str):
        """Clear screen."""
        console.clear()
        self.print_banner()
        self.print_status_bar()
    
    async def cmd_exit(self, args: str):
        """Exit shell."""
        self.running = False


def main():
    """Entry point."""
    shell = ChimeraShell()
    
    try:
        asyncio.run(shell.run())
    except KeyboardInterrupt:
        console.print("\n[cyan]Goodbye![/cyan]")


if __name__ == "__main__":
    main()
