"""Real-time telemetry dashboard for excavation (gotop-style)."""

import time
from collections import deque
from datetime import datetime
from typing import Optional

from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn, SpinnerColumn
from rich.table import Table
from rich.text import Text


class TelemetryDashboard:
    """Gotop-style telemetry dashboard for excavation."""
    
    def __init__(self, stats: dict):
        self.stats = stats
        self.start_time = datetime.now()
        self.current_file = ""
        self.feed = deque(maxlen=8)  # Last 8 files
        self.velocity_samples = deque(maxlen=60)  # 60 samples for velocity calc
        self.last_count = 0
        self.last_time = time.time()
        
        # Entity type counters
        self.entity_types = {
            "EMAIL": 0,
            "URL": 0,
            "PATH": 0,
            "DATE": 0,
            "PROPER_NOUN": 0,
        }
    
    def add_to_feed(self, message: str):
        """Add message to live feed."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.feed.append(f"[dim]{timestamp}[/dim] {message}")
    
    def get_velocity(self) -> float:
        """Calculate files per minute."""
        current_time = time.time()
        elapsed = current_time - self.last_time
        
        if elapsed >= 1.0:  # Update every second
            current_count = self.stats.get("files_processed", 0)
            velocity = (current_count - self.last_count) * 60 / elapsed
            self.velocity_samples.append(velocity)
            self.last_count = current_count
            self.last_time = current_time
        
        if self.velocity_samples:
            return sum(self.velocity_samples) / len(self.velocity_samples)
        return 0
    
    def get_uptime(self) -> str:
        """Get formatted uptime."""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        if elapsed > 3600:
            return f"{elapsed/3600:.1f}h"
        elif elapsed > 60:
            return f"{elapsed/60:.1f}m"
        else:
            return f"{elapsed:.0f}s"
    
    def make_bar(self, value: int, max_value: int, width: int = 20) -> str:
        """Create ASCII progress bar."""
        if max_value == 0:
            return "░" * width
        
        filled = min(int((value / max_value) * width), width)
        return "█" * filled + "░" * (width - filled)
    
    def make_spark(self, values: list, width: int = 20) -> str:
        """Create sparkline from values."""
        if not values:
            return "▁" * width
        
        chars = "▁▂▃▄▅▆▇█"
        min_val = min(values) if values else 0
        max_val = max(values) if values else 1
        range_val = max_val - min_val or 1
        
        # Take last 'width' samples
        samples = list(values)[-width:]
        
        spark = ""
        for v in samples:
            idx = int(((v - min_val) / range_val) * (len(chars) - 1))
            spark += chars[idx]
        
        # Pad if needed
        spark = spark.ljust(width, "▁")
        return spark
    
    def get_layout(self) -> Layout:
        """Build the full dashboard layout."""
        layout = Layout()
        
        # Main structure
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3),
        )
        
        # Body split
        layout["body"].split_row(
            Layout(name="left"),
            Layout(name="right"),
        )
        
        # Left column
        layout["left"].split_column(
            Layout(name="velocity", size=6),
            Layout(name="feed"),
        )
        
        # Right column
        layout["right"].split_column(
            Layout(name="stats", size=8),
            Layout(name="entities"),
        )
        
        # Populate panels
        layout["header"].update(self._header_panel())
        layout["velocity"].update(self._velocity_panel())
        layout["feed"].update(self._feed_panel())
        layout["stats"].update(self._stats_panel())
        layout["entities"].update(self._entities_panel())
        layout["footer"].update(self._footer_panel())
        
        return layout
    
    def _header_panel(self) -> Panel:
        """Header with status."""
        velocity = self.get_velocity()
        status = "[bold green]● EXCAVATING[/bold green]" if velocity > 0 else "[yellow]● SCANNING[/yellow]"
        
        return Panel(
            f"{status}  │  Uptime: {self.get_uptime()}  │  Velocity: {velocity:.0f} files/min",
            title="[bold cyan]CHIMERA TELEMETRY[/bold cyan]",
            border_style="cyan",
        )
    
    def _velocity_panel(self) -> Panel:
        """Velocity graph."""
        velocity = self.get_velocity()
        spark = self.make_spark(list(self.velocity_samples))
        
        content = f"""
[cyan]Files/min:[/cyan]  {velocity:>6.0f}  {spark}
[cyan]Chunks/s:[/cyan]   {self.stats.get('chunks_created', 0) / max(1, (datetime.now() - self.start_time).total_seconds()):>6.1f}
[cyan]Entities/s:[/cyan] {self.stats.get('entities_extracted', 0) / max(1, (datetime.now() - self.start_time).total_seconds()):>6.1f}
"""
        return Panel(content.strip(), title="Velocity", border_style="green")
    
    def _feed_panel(self) -> Panel:
        """Live file feed."""
        if self.feed:
            content = "\n".join(self.feed)
        else:
            content = "[dim]Waiting for files...[/dim]"
        
        # Add current file
        if self.current_file:
            short_path = self.current_file
            if len(short_path) > 50:
                short_path = "..." + short_path[-47:]
            content = f"[bold]→ {short_path}[/bold]\n" + content
        
        return Panel(content, title="Live Feed", border_style="blue")
    
    def _stats_panel(self) -> Panel:
        """Main statistics."""
        files_found = self.stats.get("files_found", 0)
        files_processed = self.stats.get("files_processed", 0)
        chunks = self.stats.get("chunks_created", 0)
        entities = self.stats.get("entities_extracted", 0)
        errors = self.stats.get("errors", 0)
        
        # Progress bar for files
        if files_found > 0:
            progress = files_processed / files_found
            bar = self.make_bar(files_processed, files_found, 15)
        else:
            progress = 0
            bar = self.make_bar(0, 1, 15)
        
        content = f"""
[cyan]Files Found:[/cyan]     {files_found:>10,}
[cyan]Files Processed:[/cyan] {files_processed:>10,}  {bar} {progress*100:>5.1f}%
[cyan]Chunks:[/cyan]          {chunks:>10,}
[cyan]Entities:[/cyan]        {entities:>10,}
[red]Errors:[/red]           {errors:>10,}
"""
        return Panel(content.strip(), title="Statistics", border_style="magenta")
    
    def _entities_panel(self) -> Panel:
        """Entity type breakdown."""
        # This would be updated by the excavator
        max_count = max(self.entity_types.values()) if self.entity_types.values() else 1
        
        lines = []
        for etype, count in sorted(self.entity_types.items(), key=lambda x: -x[1]):
            bar = self.make_bar(count, max_count, 12)
            lines.append(f"[cyan]{etype:12}[/cyan] {bar} {count:>6,}")
        
        return Panel("\n".join(lines), title="Entity Types", border_style="yellow")
    
    def _footer_panel(self) -> Panel:
        """Footer with current file."""
        short_path = self.current_file
        if len(short_path) > 80:
            short_path = "..." + short_path[-77:]
        
        return Panel(
            f"[dim]Current: {short_path}[/dim]",
            border_style="dim",
        )


class SimpleTelemetry:
    """Simpler telemetry for lower-resource systems."""
    
    def __init__(self, stats: dict):
        self.stats = stats
        self.start_time = datetime.now()
    
    def update(self, current_file: str):
        """Print simple progress update."""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        files = self.stats.get("files_processed", 0)
        velocity = files / elapsed * 60 if elapsed > 0 else 0
        
        # Simple one-line update
        short = current_file[-50:] if len(current_file) > 50 else current_file
        print(f"\r[{files:>6}] {velocity:>5.0f}/min │ {short:<50}", end="", flush=True)
