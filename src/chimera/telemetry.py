"""Real-time telemetry dashboard for CHIMERA.

Provides live monitoring of daemon status, extraction progress,
and system metrics using Rich's Live display.
"""

import asyncio
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import httpx
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.text import Text

console = Console()

DEFAULT_API_URL = "http://127.0.0.1:7777"


@dataclass
class TelemetryState:
    """Current telemetry state."""
    # Connection
    connected: bool = False
    last_update: datetime | None = None
    error: str | None = None

    # Daemon stats
    uptime_seconds: float = 0
    version: str = "unknown"

    # Catalog stats
    total_files: int = 0
    total_chunks: int = 0
    total_entities: int = 0
    discoveries_count: int = 0

    # Live stats
    files_indexed: int = 0
    jobs_processed: int = 0
    jobs_pending: int = 0
    correlations_run: int = 0

    # Entity breakdown
    entities_by_type: dict[str, int] = field(default_factory=dict)

    # Patterns/Discoveries
    patterns_detected: int = 0
    discoveries_by_type: dict[str, int] = field(default_factory=dict)
    top_discoveries: list[dict] = field(default_factory=list)

    # Current operation (with ETA)
    current_job: dict | None = None
    current_job_eta: float | None = None

    # Recent jobs
    recent_jobs: list[dict] = field(default_factory=list)

    # Live feed (recent files)
    live_feed: deque = field(default_factory=lambda: deque(maxlen=5))

    # Velocity tracking
    files_history: deque = field(default_factory=lambda: deque(maxlen=60))
    chunks_history: deque = field(default_factory=lambda: deque(maxlen=60))

    # System (real stats from psutil)
    cpu_percent: float = 0
    memory_used_gb: float = 0
    memory_total_gb: float = 16.0
    memory_percent: float = 0
    disk_read_mb: float = 0
    disk_write_mb: float = 0
    _prev_disk_read: int = 0
    _prev_disk_write: int = 0

    # GPU
    gpu_available: bool = False
    gpu_name: str = ""
    gpu_memory_used_gb: float = 0
    gpu_memory_total_gb: float = 0
    gpu_utilization: float = 0

    # Storage
    vectors_size_gb: float = 0
    catalog_size_mb: float = 0


def api_request(endpoint: str, timeout: float = 5.0) -> dict | None:
    """Make API request to daemon."""
    try:
        response = httpx.get(f"{DEFAULT_API_URL}{endpoint}", timeout=timeout)
        return response.json()
    except Exception:
        return None


def create_sparkline(values: list[float], width: int = 20) -> str:
    """Create ASCII sparkline from values."""
    if not values:
        return "▁" * width

    chars = "▁▂▃▄▅▆▇█"
    min_val = min(values) if values else 0
    max_val = max(values) if values else 1
    range_val = max_val - min_val or 1

    # Take last `width` values
    recent = list(values)[-width:]

    sparkline = ""
    for v in recent:
        idx = int((v - min_val) / range_val * (len(chars) - 1))
        sparkline += chars[idx]

    # Pad if needed
    sparkline = sparkline.ljust(width, "▁")
    return sparkline


def create_bar(value: float, max_value: float, width: int = 20, filled: str = "█", empty: str = "░") -> str:
    """Create progress bar."""
    if max_value == 0:
        return empty * width
    ratio = min(1.0, value / max_value)
    filled_count = int(ratio * width)
    return filled * filled_count + empty * (width - filled_count)


def format_uptime(seconds: float) -> str:
    """Format uptime as human readable."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds/60:.0f}m"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def format_number(n: int) -> str:
    """Format large numbers with commas."""
    return f"{n:,}"


def format_elapsed(seconds: float | None) -> str:
    """Format elapsed time."""
    if seconds is None:
        return "..."
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        return f"{seconds/3600:.1f}h"


class TelemetryDashboard:
    """Real-time telemetry dashboard."""

    def __init__(self, refresh_rate: float = 1.0):
        self.refresh_rate = refresh_rate
        self.state = TelemetryState()
        self.running = False
        self.start_time = time.time()
        self._prev_files = 0
        self._prev_chunks = 0
        self._prev_time = time.time()

    def fetch_status(self) -> None:
        """Fetch current status from daemon using telemetry endpoint."""
        # Use comprehensive telemetry endpoint
        telemetry = api_request("/api/v1/telemetry")
        if telemetry is None or telemetry.get("error"):
            self.state.connected = False
            self.state.error = telemetry.get("error") if telemetry else "Connection failed"
            return

        self.state.connected = True
        self.state.error = None
        self.state.last_update = datetime.now()

        # Status info
        status = telemetry.get("status", {})
        self.state.version = status.get("version", "unknown")
        self.state.uptime_seconds = status.get("uptime_seconds", 0)

        stats = status.get("stats", {})
        self.state.files_indexed = stats.get("files_indexed", 0)
        self.state.jobs_processed = stats.get("jobs_processed", 0)
        self.state.correlations_run = stats.get("correlations_run", 0)
        self.state.discoveries_count = stats.get("discoveries_surfaced", 0)

        catalog = status.get("catalog", {})
        self.state.total_files = catalog.get("total_files", 0)
        self.state.total_chunks = catalog.get("total_chunks", 0)
        self.state.total_entities = catalog.get("total_entities", 0)

        # System stats (real from psutil)
        system = telemetry.get("system", {})
        self.state.cpu_percent = system.get("cpu_percent", 0)
        self.state.memory_used_gb = system.get("memory_used_gb", 0)
        self.state.memory_total_gb = system.get("memory_total_gb", 16)
        self.state.memory_percent = system.get("memory_percent", 0)

        # Disk I/O (calculate rate)
        disk_read = system.get("disk_read_bytes", 0)
        disk_write = system.get("disk_write_bytes", 0)
        if self.state._prev_disk_read > 0:
            self.state.disk_read_mb = (disk_read - self.state._prev_disk_read) / (1024 * 1024)
            self.state.disk_write_mb = (disk_write - self.state._prev_disk_write) / (1024 * 1024)
        self.state._prev_disk_read = disk_read
        self.state._prev_disk_write = disk_write

        # GPU info
        gpu = telemetry.get("gpu", {})
        self.state.gpu_available = gpu.get("available", False)
        self.state.gpu_name = gpu.get("device", "")
        self.state.gpu_memory_used_gb = gpu.get("memory_used_gb", 0)
        self.state.gpu_memory_total_gb = gpu.get("memory_total_gb", 0)
        self.state.gpu_utilization = gpu.get("utilization_percent", 0)

        # Storage
        storage = telemetry.get("storage", {})
        self.state.catalog_size_mb = storage.get("catalog_mb", 0)
        self.state.vectors_size_gb = storage.get("vectors_gb", 0)

        # Current job (with ETA)
        current_job = telemetry.get("current_job")
        self.state.current_job = current_job
        if current_job:
            self.state.current_job_eta = current_job.get("eta_seconds")
        else:
            self.state.current_job_eta = None

        # Patterns detected count
        self.state.patterns_detected = telemetry.get("patterns_detected", 0)

        # Calculate velocity
        now = time.time()
        elapsed = now - self._prev_time
        if elapsed > 0:
            files_per_sec = (self.state.total_files - self._prev_files) / elapsed
            chunks_per_sec = (self.state.total_chunks - self._prev_chunks) / elapsed
            self.state.files_history.append(files_per_sec * 60)  # per minute
            self.state.chunks_history.append(chunks_per_sec * 60)

        self._prev_files = self.state.total_files
        self._prev_chunks = self.state.total_chunks
        self._prev_time = now

        # Get entities by type from telemetry response
        entities_by_type = telemetry.get("entities_by_type", {})
        if entities_by_type:
            self.state.entities_by_type = entities_by_type

        # Get jobs info
        jobs = api_request("/api/v1/jobs")
        if jobs:
            self.state.jobs_pending = jobs.get("pending", 0)

        # Get recent jobs for live feed
        recent = api_request("/api/v1/jobs/recent?limit=5")
        if recent and recent.get("jobs"):
            self.state.recent_jobs = recent["jobs"]

        # Get discoveries from telemetry
        discoveries_by_type = telemetry.get("discoveries_by_type", {})
        if discoveries_by_type:
            self.state.discoveries_by_type = discoveries_by_type

        top_discoveries = telemetry.get("top_discoveries", [])
        if top_discoveries:
            self.state.top_discoveries = top_discoveries

    def make_cpu_panel(self) -> Panel:
        """Create CPU panel with real stats."""
        cpu_bar = create_bar(self.state.cpu_percent, 100, width=15)
        load = self.state.jobs_pending / 10 if self.state.jobs_pending else 0.1

        content = Text()
        content.append(f"CPU: {self.state.cpu_percent:.0f}%".ljust(12))
        content.append(f"Load: {load:.2f}\n", style="dim")
        color = "green" if self.state.cpu_percent < 50 else "yellow" if self.state.cpu_percent < 80 else "red"
        content.append(cpu_bar, style=color)

        return Panel(content, title="[bold]cpu[/bold]", border_style="dim")

    def make_velocity_panel(self) -> Panel:
        """Create extraction velocity panel."""
        files_per_min = self.state.files_history[-1] if self.state.files_history else 0
        chunks_per_min = self.state.chunks_history[-1] if self.state.chunks_history else 0

        sparkline = create_sparkline(list(self.state.files_history), width=25)

        content = Text()
        content.append(f"{sparkline}\n", style="cyan")
        content.append(f"-> {files_per_min:,.0f} files/m\n", style="green")
        content.append(f"-> {chunks_per_min:,.1f}k chunks/m", style="green")

        return Panel(content, title="[bold]extraction velocity[/bold]", border_style="dim")

    def make_memory_panel(self) -> Panel:
        """Create memory panel with real stats."""
        mem_bar = create_bar(self.state.memory_used_gb, self.state.memory_total_gb, width=15)

        content = Text()
        content.append(f"{mem_bar} {self.state.memory_used_gb:.1f} / {self.state.memory_total_gb:.0f}G\n")
        content.append(f"Vectors: {self.state.vectors_size_gb:.2f}G  ", style="dim")
        content.append(f"Catalog: {self.state.catalog_size_mb:.0f}M", style="dim")

        return Panel(content, title="[bold]memory[/bold]", border_style="dim")

    def make_entities_panel(self) -> Panel:
        """Create entities extracted panel."""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Type", width=8)
        table.add_column("Bar", width=12)
        table.add_column("Count", justify="right", width=8)

        # Get top 5 entity types
        sorted_types = sorted(
            self.state.entities_by_type.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]

        max_count = sorted_types[0][1] if sorted_types else 1

        for etype, count in sorted_types:
            bar = create_bar(count, max_count, width=12, filled="█", empty="░")
            table.add_row(etype[:8], f"[cyan]{bar}[/cyan]", format_number(count))

        return Panel(table, title="[bold]entities extracted[/bold]", border_style="dim")

    def make_disk_panel(self) -> Panel:
        """Create disk I/O panel with real stats."""
        read_speed = max(0, self.state.disk_read_mb)
        write_speed = max(0, self.state.disk_write_mb)

        read_spark = create_sparkline([read_speed] * 10, width=8)
        write_spark = create_sparkline([write_speed] * 10, width=8)

        content = Text()
        content.append(f"Read:  {read_spark} {read_speed:,.0f} MB/s\n")
        content.append(f"Write: {write_spark} {write_speed:,.0f} MB/s")

        return Panel(content, title="[bold]disk i/o[/bold]", border_style="dim")

    def make_current_op_panel(self) -> Panel:
        """Create current operation panel showing what's running with ETA."""
        content = Text()

        if self.state.current_job:
            job = self.state.current_job
            job_type = job.get("type", "unknown")
            elapsed = job.get("elapsed_seconds")
            eta = job.get("eta_seconds")
            payload = job.get("payload", {}) or job.get("details", {})

            # Format job type nicely
            type_display = job_type.replace("_", " ").title()

            # Show spinner-like indicator
            spinner_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
            spinner_idx = int(time.time() * 4) % len(spinner_chars)
            spinner = spinner_chars[spinner_idx]

            content.append(f"{spinner} ", style="cyan bold")
            content.append(f"{type_display}\n", style="bold")
            content.append(f"  Elapsed: {format_elapsed(elapsed)}", style="dim")

            # Show ETA if available
            if eta is not None and eta > 0:
                content.append(f" | ETA: {format_elapsed(eta)}\n", style="yellow")
            else:
                content.append("\n")

            # Show progress bar if we have ETA
            if eta is not None and elapsed is not None and (elapsed + eta) > 0:
                progress = elapsed / (elapsed + eta)
                bar = create_bar(progress * 100, 100, width=30)
                content.append(f"  {bar} {progress:.0%}\n", style="cyan")

            # Show source (sync_api vs queued_job)
            source = payload.get("source", "")
            if source == "sync_api":
                content.append("  [CLI: --now]\n", style="magenta dim")

            # Show relevant payload info
            if "path" in payload:
                path = payload["path"]
                if len(path) > 30:
                    path = "..." + path[-27:]
                content.append(f"  {path}", style="dim")
            elif "scope" in payload:
                scope = payload["scope"]
                parts = []
                if scope.get("files"):
                    parts.append("files")
                if scope.get("fae"):
                    parts.append("fae")
                if scope.get("correlate"):
                    parts.append("correlate")
                content.append(f"  Scope: {', '.join(parts)}", style="dim")
        else:
            content.append("Idle", style="dim")
            content.append(" - no operation running\n\n", style="dim")
            content.append("Commands:\n", style="cyan")
            content.append("  chimera correlate --now\n", style="dim")
            content.append("  chimera excavate", style="dim")

        return Panel(content, title="[bold]current operation[/bold]", border_style="cyan")

    def make_gpu_panel(self) -> Panel:
        """Create GPU panel."""
        content = Text()

        if self.state.gpu_available:
            # GPU name
            content.append(f"{self.state.gpu_name[:25]}\n", style="green bold")

            # Utilization bar
            util_bar = create_bar(self.state.gpu_utilization, 100, width=10)
            util_color = "green" if self.state.gpu_utilization < 50 else "yellow" if self.state.gpu_utilization < 80 else "red"
            content.append(f"GPU: {util_bar} ", style=util_color)
            content.append(f"{self.state.gpu_utilization:.0f}%\n", style=util_color)

            # Memory bar
            mem_bar = create_bar(self.state.gpu_memory_used_gb, self.state.gpu_memory_total_gb, width=10)
            content.append(f"Mem: {mem_bar} ", style="cyan")
            content.append(f"{self.state.gpu_memory_used_gb:.1f}/{self.state.gpu_memory_total_gb:.1f}G", style="dim")
        else:
            content.append("No GPU detected", style="dim")

        return Panel(content, title="[bold]gpu[/bold]", border_style="dim")

    def make_discoveries_panel(self) -> Panel:
        """Create discoveries panel showing correlation results with patterns."""
        content = Text()

        # Show patterns count prominently
        if self.state.patterns_detected > 0:
            content.append("Patterns: ", style="bold magenta")
            content.append(f"{self.state.patterns_detected:,}\n", style="magenta")

        # Show discovery counts by type
        total = sum(self.state.discoveries_by_type.values())
        if total == 0 and self.state.patterns_detected == 0:
            content.append("No discoveries yet - run correlation", style="dim")
            return Panel(
                content,
                title="[bold]correlation results[/bold]",
                border_style="dim"
            )

        # Show totals by type
        if total > 0:
            content.append("Discoveries: ", style="bold yellow")
            content.append(f"{total:,}\n", style="yellow")
            for dtype, count in sorted(self.state.discoveries_by_type.items(), key=lambda x: -x[1]):
                content.append(f"  {dtype}: ", style="dim")
                content.append(f"{count:,}\n", style="cyan")

        # Show top discoveries if available
        if self.state.top_discoveries:
            content.append("\nTop:\n", style="bold")
            for d in self.state.top_discoveries[:3]:
                conf = d.get("confidence", 0)
                title = d.get("title", "")[:25]
                color = "green" if conf >= 0.8 else "yellow" if conf >= 0.6 else "dim"
                content.append(f"  [{conf:.0%}] ", style=color)
                content.append(f"{title}\n", style="dim")

        return Panel(content, title="[bold]correlation results[/bold]", border_style="dim")

    def make_feed_panel(self) -> Panel:
        """Create live feed panel showing recent jobs with timestamps."""
        content = Text()

        if not self.state.recent_jobs:
            content.append("No recent activity", style="dim")
        else:
            for job in self.state.recent_jobs[:5]:
                status = job.get("status", "unknown")
                job_type = job.get("type", "unknown")
                payload = job.get("payload", {})
                completed_at = job.get("completed_at", "")

                # Timestamp (show time only)
                if completed_at:
                    try:
                        ts = completed_at.split("T")[1][:8]  # HH:MM:SS
                        content.append(f"{ts} ", style="dim")
                    except Exception:
                        content.append("         ", style="dim")
                else:
                    content.append("         ", style="dim")

                # Status icon with proper styling
                if status == "completed":
                    content.append("OK ", style="green")
                elif status == "running":
                    content.append(">> ", style="cyan bold")
                elif status == "failed":
                    content.append("!! ", style="red")
                else:
                    content.append("-- ", style="dim")

                # Path or type (shorter to fit timestamp)
                if "path" in payload:
                    path = payload["path"]
                    if len(path) > 22:
                        path = "..." + path[-19:]
                    content.append(f"{path}\n")
                else:
                    type_short = job_type.replace("_", " ")[:22]
                    content.append(f"{type_short}\n")

        return Panel(content, title="[bold]live feed[/bold]", border_style="dim")

    def make_stats_panel(self) -> Panel:
        """Create catalog stats panel."""
        uptime = format_uptime(self.state.uptime_seconds)

        content = Text()
        content.append(f"Files: {format_number(self.state.total_files)}".ljust(18))
        content.append(f"Chunks: {format_number(self.state.total_chunks)}".ljust(20))
        content.append(f"Entities: {format_number(self.state.total_entities)}".ljust(22))
        content.append(f"Discoveries: {self.state.discoveries_count}".ljust(18))
        content.append(f"Uptime: {uptime}")

        return Panel(content, title="[bold]catalog stats[/bold]", border_style="dim")

    def make_status_bar(self) -> Text:
        """Create status bar."""
        status = Text()

        if self.state.connected:
            status.append("* ", style="green bold")
            status.append("CHIMERA ", style="bold")
            status.append(f"v{self.state.version} ", style="dim")
            status.append("| ", style="dim")
            status.append(f"Jobs: {self.state.jobs_pending} pending ", style="cyan")
            status.append("| ", style="dim")
            if self.state.last_update:
                status.append(f"Updated: {self.state.last_update.strftime('%H:%M:%S')}", style="dim")
        else:
            status.append("* ", style="red bold")
            status.append("CHIMERA ", style="bold")
            status.append("| ", style="dim")
            status.append(f"Disconnected: {self.state.error or 'No connection'}", style="red")

        return status

    def make_job_queue_panel(self) -> Panel:
        """Create job queue status panel."""
        content = Text()

        content.append("Pending: ", style="dim")
        content.append(f"{self.state.jobs_pending}\n", style="cyan" if self.state.jobs_pending > 0 else "green")

        content.append("Processed: ", style="dim")
        content.append(f"{self.state.jobs_processed:,}\n", style="green")

        content.append("Correlations: ", style="dim")
        content.append(f"{self.state.correlations_run}\n", style="cyan")

        return Panel(content, title="[bold]job queue[/bold]", border_style="dim")

    def make_storage_panel(self) -> Panel:
        """Create storage stats panel."""
        content = Text()

        content.append("Catalog: ", style="dim")
        content.append(f"{self.state.catalog_size_mb:,.0f} MB\n", style="cyan")

        content.append("Vectors: ", style="dim")
        content.append(f"{self.state.vectors_size_gb:.2f} GB\n", style="cyan")

        # Calculate total
        total_gb = self.state.catalog_size_mb / 1024 + self.state.vectors_size_gb
        content.append("Total: ", style="dim")
        content.append(f"{total_gb:.2f} GB", style="bold")

        return Panel(content, title="[bold]storage[/bold]", border_style="dim")

    def make_layout(self) -> Layout:
        """Create the dashboard layout."""
        layout = Layout()

        # Main structure
        layout.split_column(
            Layout(name="header", size=1),
            Layout(name="top", size=12),
            Layout(name="middle", size=10),
            Layout(name="bottom", size=10),
            Layout(name="footer", size=1),
        )

        # Header
        layout["header"].update(self.make_status_bar())

        # Top row - system stats
        layout["top"].split_row(
            Layout(name="left_top", ratio=1),
            Layout(name="right_top", ratio=1),
        )

        layout["left_top"].split_column(
            Layout(name="cpu", size=4),
            Layout(name="memory", size=4),
            Layout(name="gpu", size=4),
        )

        layout["right_top"].split_column(
            Layout(name="velocity", size=5),
            Layout(name="entities", size=7),
        )

        # Middle row - activity
        layout["middle"].split_row(
            Layout(name="feed", ratio=1),
            Layout(name="discoveries", ratio=1),
        )

        # Bottom row - current operation + queue
        layout["bottom"].split_row(
            Layout(name="current_op", ratio=2),
            Layout(name="queue_storage", ratio=1),
        )

        layout["queue_storage"].split_column(
            Layout(name="job_queue", size=5),
            Layout(name="storage", size=5),
        )

        # Populate panels
        layout["cpu"].update(self.make_cpu_panel())
        layout["memory"].update(self.make_memory_panel())
        layout["gpu"].update(self.make_gpu_panel())
        layout["velocity"].update(self.make_velocity_panel())
        layout["entities"].update(self.make_entities_panel())
        layout["feed"].update(self.make_feed_panel())
        layout["discoveries"].update(self.make_discoveries_panel())
        layout["current_op"].update(self.make_current_op_panel())
        layout["job_queue"].update(self.make_job_queue_panel())
        layout["storage"].update(self.make_storage_panel())

        # Footer with catalog stats
        footer = Text()
        footer.append(f"Files: {self.state.total_files:,}", style="cyan")
        footer.append(" | ", style="dim")
        footer.append(f"Chunks: {self.state.total_chunks:,}", style="cyan")
        footer.append(" | ", style="dim")
        footer.append(f"Entities: {self.state.total_entities:,}", style="cyan")
        footer.append(" | ", style="dim")
        footer.append(f"Uptime: {format_uptime(self.state.uptime_seconds)}", style="dim")
        footer.append(" | Press Ctrl+C to exit", style="dim")
        layout["footer"].update(footer)

        return layout

    def run(self) -> None:
        """Run the dashboard (blocking)."""
        self.running = True

        with Live(self.make_layout(), refresh_per_second=2, screen=True) as live:
            try:
                while self.running:
                    self.fetch_status()
                    live.update(self.make_layout())
                    time.sleep(self.refresh_rate)
            except KeyboardInterrupt:
                self.running = False


class CommandTelemetry:
    """Telemetry helpers for individual commands."""

    def __init__(self):
        self.console = Console()

    def with_spinner(self, message: str):
        """Context manager for spinner."""
        return self.console.status(f"[cyan]{message}[/cyan]", spinner="dots")

    def success(self, message: str) -> None:
        """Print success message."""
        self.console.print(f"[green]OK[/green] {message}")

    def error(self, message: str, detail: str | None = None) -> None:
        """Print error message."""
        self.console.print(f"[red]!![/red] {message}")
        if detail:
            self.console.print(f"  [dim]{detail}[/dim]")

    def warning(self, message: str) -> None:
        """Print warning message."""
        self.console.print(f"[yellow]!![/yellow] {message}")

    def info(self, message: str) -> None:
        """Print info message."""
        self.console.print(f"[blue]--[/blue] {message}")

    def progress(self, message: str, current: int, total: int) -> None:
        """Print progress update."""
        pct = (current / total * 100) if total > 0 else 0
        bar = create_bar(current, total, width=20)
        self.console.print(f"  {bar} {pct:.0f}% {message}")

    def status_dot(self, running: bool) -> str:
        """Return colored status dot."""
        return "[green]*[/green]" if running else "[red]*[/red]"

    def api_call(self, method: str, endpoint: str, description: str, **kwargs) -> tuple[dict | None, str | None]:
        """Make API call with telemetry."""
        try:
            with self.with_spinner(description):
                if method.upper() == "GET":
                    response = httpx.get(f"{DEFAULT_API_URL}{endpoint}", timeout=30, **kwargs)
                else:
                    response = httpx.post(f"{DEFAULT_API_URL}{endpoint}", timeout=30, **kwargs)

                result = response.json()

                if response.status_code >= 400:
                    return None, f"HTTP {response.status_code}: {result.get('error', 'Unknown error')}"

                if result.get("error"):
                    return None, result["error"]

                return result, None

        except httpx.ConnectError:
            return None, "Cannot connect to daemon. Is it running?"
        except httpx.TimeoutException:
            return None, "Request timed out"
        except Exception as e:
            return None, str(e)


# Singleton for command telemetry
_telemetry: CommandTelemetry | None = None


def get_telemetry() -> CommandTelemetry:
    """Get command telemetry instance."""
    global _telemetry
    if _telemetry is None:
        _telemetry = CommandTelemetry()
    return _telemetry


def run_dashboard(refresh_rate: float = 1.0) -> None:
    """Run the telemetry dashboard (blocking)."""
    dashboard = TelemetryDashboard(refresh_rate=refresh_rate)
    dashboard.run()


def run_dashboard_background(refresh_rate: float = 1.0) -> threading.Thread:
    """Run the telemetry dashboard in a background thread (non-blocking).

    Returns the thread so it can be joined or stopped.
    """
    def _run():
        dashboard = TelemetryDashboard(refresh_rate=refresh_rate)
        dashboard.run()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread
