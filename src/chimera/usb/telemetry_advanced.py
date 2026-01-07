"""Advanced Gotop-style Telemetry Dashboard.

Full real-time visualization with:
- CPU/Memory sparklines
- Entity type distribution bars
- Velocity graphs
- Live file feed
- Pattern detection indicators
"""

import asyncio
import time
from collections import deque
from datetime import datetime
from typing import Optional, Dict, List

try:
    from textual.app import App, ComposeResult
    from textual.containers import Container, Horizontal, Vertical
    from textual.widgets import Header, Footer, Static, ProgressBar, Label
    from textual.reactive import reactive
    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False

from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn, SpinnerColumn, TaskProgressColumn
from rich.table import Table
from rich.text import Text

console = Console()


class SparklineGenerator:
    """Generate ASCII sparklines from data."""
    
    CHARS = "▁▂▃▄▅▆▇█"
    
    @classmethod
    def generate(cls, values: list, width: int = 20) -> str:
        """Create sparkline from values."""
        if not values:
            return cls.CHARS[0] * width
        
        # Normalize to available chars
        min_val = min(values)
        max_val = max(values)
        range_val = max_val - min_val or 1
        
        # Take last 'width' samples
        samples = list(values)[-width:]
        
        spark = ""
        for v in samples:
            idx = int(((v - min_val) / range_val) * (len(cls.CHARS) - 1))
            spark += cls.CHARS[idx]
        
        # Pad if needed
        return spark.ljust(width, cls.CHARS[0])


class BarGenerator:
    """Generate ASCII progress bars."""
    
    FILLED = "█"
    PARTIAL = "▓▒░"
    EMPTY = "░"
    
    @classmethod
    def generate(cls, value: float, max_value: float, width: int = 20) -> str:
        """Create progress bar."""
        if max_value == 0:
            return cls.EMPTY * width
        
        ratio = min(value / max_value, 1.0)
        filled = int(ratio * width)
        
        return cls.FILLED * filled + cls.EMPTY * (width - filled)
    
    @classmethod
    def generate_labeled(cls, label: str, value: float, max_value: float, 
                         width: int = 15, color: str = "cyan") -> str:
        """Create labeled progress bar."""
        bar = cls.generate(value, max_value, width)
        return f"[{color}]{label:12}[/{color}] {bar} {value:>8,.0f}"


class LiveMetrics:
    """Track live metrics with history for sparklines."""
    
    def __init__(self, history_size: int = 60):
        self.history_size = history_size
        self.files_per_second = deque(maxlen=history_size)
        self.chunks_per_second = deque(maxlen=history_size)
        self.entities_per_second = deque(maxlen=history_size)
        self.cpu_usage = deque(maxlen=history_size)
        self.memory_usage = deque(maxlen=history_size)
        
        self._last_update = time.time()
        self._last_files = 0
        self._last_chunks = 0
        self._last_entities = 0
    
    def update(self, stats: dict):
        """Update metrics from stats dict."""
        now = time.time()
        elapsed = now - self._last_update
        
        if elapsed >= 1.0:  # Update every second
            files = stats.get("files_processed", 0)
            chunks = stats.get("chunks_created", 0)
            entities = stats.get("entities_extracted", 0)
            
            self.files_per_second.append((files - self._last_files) / elapsed)
            self.chunks_per_second.append((chunks - self._last_chunks) / elapsed)
            self.entities_per_second.append((entities - self._last_entities) / elapsed)
            
            self._last_files = files
            self._last_chunks = chunks
            self._last_entities = entities
            self._last_update = now
            
            # Try to get system metrics
            try:
                import psutil
                self.cpu_usage.append(psutil.cpu_percent())
                self.memory_usage.append(psutil.virtual_memory().percent)
            except:
                pass
    
    def get_velocity(self, metric: str) -> float:
        """Get average velocity for a metric."""
        data = getattr(self, metric, [])
        if not data:
            return 0
        return sum(data) / len(data)


class AdvancedTelemetryDashboard:
    """Full gotop-style dashboard using Rich."""
    
    def __init__(self, stats: dict):
        self.stats = stats
        self.metrics = LiveMetrics()
        self.start_time = datetime.now()
        self.current_file = ""
        self.feed = deque(maxlen=10)
        
        # Entity type tracking
        self.entity_types: Dict[str, int] = {
            "PERSON": 0,
            "ORG": 0,
            "TECH": 0,
            "DATE": 0,
            "LOC": 0,
            "EMAIL": 0,
            "URL": 0,
            "PATH": 0,
        }
        
        # Pattern tracking
        self.patterns: List[dict] = []
    
    def add_to_feed(self, message: str, status: str = "ok"):
        """Add message to live feed."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        icon = "✓" if status == "ok" else "✗" if status == "error" else "⟳"
        color = "green" if status == "ok" else "red" if status == "error" else "yellow"
        self.feed.append(f"[dim]{timestamp}[/dim] [{color}]{icon}[/{color}] {message}")
    
    def update_entity_type(self, entity_type: str, count: int = 1):
        """Update entity type counter."""
        if entity_type in self.entity_types:
            self.entity_types[entity_type] += count
        else:
            # Map to closest category
            type_map = {
                "PROPER_NOUN": "PERSON",
                "GPE": "LOC",
                "ORGANIZATION": "ORG",
                "TECHNOLOGY": "TECH",
            }
            mapped = type_map.get(entity_type, "TECH")
            self.entity_types[mapped] = self.entity_types.get(mapped, 0) + count
    
    def add_pattern(self, pattern: dict):
        """Add detected pattern."""
        self.patterns.append(pattern)
        self.patterns = sorted(self.patterns, key=lambda x: -x.get("confidence", 0))[:5]
    
    def get_uptime(self) -> str:
        """Get formatted uptime."""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        if elapsed > 3600:
            return f"{elapsed/3600:.1f}h"
        elif elapsed > 60:
            return f"{elapsed/60:.1f}m"
        return f"{elapsed:.0f}s"
    
    def build_header(self) -> Panel:
        """Build header panel."""
        velocity = self.metrics.get_velocity("files_per_second") * 60
        status = "[bold green]● EXCAVATING[/bold green]" if velocity > 0 else "[yellow]● SCANNING[/yellow]"
        
        return Panel(
            f"{status}  │  ⏱ {self.get_uptime()}  │  🚀 {velocity:.0f} files/min  │  "
            f"📁 {self.stats.get('files_processed', 0):,}  │  "
            f"🧩 {self.stats.get('chunks_created', 0):,}  │  "
            f"🏷️ {self.stats.get('entities_extracted', 0):,}",
            title="[bold cyan]CHIMERA EXCAVATOR[/bold cyan]",
            border_style="cyan",
        )
    
    def build_velocity_panel(self) -> Panel:
        """Build velocity sparklines panel."""
        self.metrics.update(self.stats)
        
        files_spark = SparklineGenerator.generate(list(self.metrics.files_per_second))
        chunks_spark = SparklineGenerator.generate(list(self.metrics.chunks_per_second))
        entities_spark = SparklineGenerator.generate(list(self.metrics.entities_per_second))
        
        files_vel = self.metrics.get_velocity("files_per_second") * 60
        chunks_vel = self.metrics.get_velocity("chunks_per_second")
        entities_vel = self.metrics.get_velocity("entities_per_second")
        
        content = f"""
[cyan]Files/min:[/cyan]    {files_vel:>6.0f}  [green]{files_spark}[/green]
[cyan]Chunks/sec:[/cyan]   {chunks_vel:>6.1f}  [yellow]{chunks_spark}[/yellow]
[cyan]Entities/sec:[/cyan] {entities_vel:>6.1f}  [magenta]{entities_spark}[/magenta]
"""
        return Panel(content.strip(), title="Velocity", border_style="green")
    
    def build_system_panel(self) -> Panel:
        """Build system metrics panel."""
        try:
            import psutil
            cpu = psutil.cpu_percent()
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            cpu_bar = BarGenerator.generate(cpu, 100, 15)
            mem_bar = BarGenerator.generate(mem.percent, 100, 15)
            disk_bar = BarGenerator.generate(disk.percent, 100, 15)
            
            cpu_spark = SparklineGenerator.generate(list(self.metrics.cpu_usage), 10)
            mem_spark = SparklineGenerator.generate(list(self.metrics.memory_usage), 10)
            
            content = f"""
[cyan]CPU:[/cyan]  {cpu_bar} {cpu:>5.1f}%  {cpu_spark}
[cyan]MEM:[/cyan]  {mem_bar} {mem.percent:>5.1f}%  {mem_spark}
[cyan]DISK:[/cyan] {disk_bar} {disk.percent:>5.1f}%
"""
        except ImportError:
            content = "[dim]psutil not installed[/dim]"
        
        return Panel(content.strip(), title="System", border_style="blue")
    
    def build_entities_panel(self) -> Panel:
        """Build entity distribution panel."""
        max_count = max(self.entity_types.values()) if self.entity_types.values() else 1
        
        lines = []
        colors = {
            "PERSON": "green",
            "ORG": "cyan",
            "TECH": "yellow",
            "DATE": "magenta",
            "LOC": "blue",
            "EMAIL": "red",
            "URL": "white",
            "PATH": "dim",
        }
        
        for etype, count in sorted(self.entity_types.items(), key=lambda x: -x[1]):
            if count > 0:
                bar = BarGenerator.generate(count, max_count, 12)
                color = colors.get(etype, "white")
                lines.append(f"[{color}]{etype:8}[/{color}] {bar} {count:>6,}")
        
        if not lines:
            lines = ["[dim]No entities yet...[/dim]"]
        
        return Panel("\n".join(lines[:8]), title="Entities", border_style="yellow")
    
    def build_feed_panel(self) -> Panel:
        """Build live file feed panel."""
        # Current file at top
        if self.current_file:
            short = self.current_file[-50:] if len(self.current_file) > 50 else self.current_file
            header = f"[bold]→ {short}[/bold]\n"
        else:
            header = ""
        
        if self.feed:
            content = header + "\n".join(self.feed)
        else:
            content = header + "[dim]Waiting for files...[/dim]"
        
        return Panel(content, title="Live Feed", border_style="magenta")
    
    def build_patterns_panel(self) -> Panel:
        """Build detected patterns panel."""
        if self.patterns:
            lines = []
            for p in self.patterns[:5]:
                conf = p.get("confidence", 0)
                bar = BarGenerator.generate(conf, 1.0, 10)
                name = p.get("name", "Unknown")[:20]
                color = "green" if conf > 0.7 else "yellow" if conf > 0.4 else "dim"
                lines.append(f"[{color}]{bar}[/{color}] [{conf:.0%}] {name}")
            content = "\n".join(lines)
        else:
            content = "[dim]Patterns will appear after correlation...[/dim]"
        
        return Panel(content, title="Patterns", border_style="cyan")
    
    def build_progress_panel(self) -> Panel:
        """Build overall progress panel."""
        files_found = self.stats.get("files_found", 0)
        files_processed = self.stats.get("files_processed", 0)
        
        if files_found > 0:
            progress = files_processed / files_found
            bar = BarGenerator.generate(files_processed, files_found, 30)
            eta = "calculating..."
            
            velocity = self.metrics.get_velocity("files_per_second")
            if velocity > 0:
                remaining = files_found - files_processed
                eta_seconds = remaining / velocity
                if eta_seconds > 3600:
                    eta = f"{eta_seconds/3600:.1f}h"
                elif eta_seconds > 60:
                    eta = f"{eta_seconds/60:.0f}m"
                else:
                    eta = f"{eta_seconds:.0f}s"
            
            content = f"""
[cyan]Progress:[/cyan] {bar} {progress*100:>5.1f}%

[dim]Files:[/dim] {files_processed:,} / {files_found:,}
[dim]ETA:[/dim] {eta}
[dim]Errors:[/dim] {self.stats.get('errors', 0)}
"""
        else:
            content = "[dim]Scanning for files...[/dim]"
        
        return Panel(content.strip(), title="Progress", border_style="green")
    
    def get_layout(self) -> Layout:
        """Build complete dashboard layout."""
        layout = Layout()
        
        # Main structure
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=5),
        )
        
        # Body: 2 columns
        layout["body"].split_row(
            Layout(name="left"),
            Layout(name="right"),
        )
        
        # Left column
        layout["left"].split_column(
            Layout(name="velocity", size=6),
            Layout(name="system", size=6),
            Layout(name="feed"),
        )
        
        # Right column
        layout["right"].split_column(
            Layout(name="entities", size=10),
            Layout(name="patterns"),
        )
        
        # Populate
        layout["header"].update(self.build_header())
        layout["velocity"].update(self.build_velocity_panel())
        layout["system"].update(self.build_system_panel())
        layout["feed"].update(self.build_feed_panel())
        layout["entities"].update(self.build_entities_panel())
        layout["patterns"].update(self.build_patterns_panel())
        layout["footer"].update(self.build_progress_panel())
        
        return layout


class MinimalTelemetry:
    """Minimal telemetry for resource-constrained systems."""
    
    def __init__(self, stats: dict):
        self.stats = stats
        self.start_time = time.time()
        self.last_update = time.time()
        self.last_files = 0
    
    def update(self, current_file: str = ""):
        """Print simple progress line."""
        now = time.time()
        elapsed = now - self.start_time
        files = self.stats.get("files_processed", 0)
        
        # Calculate velocity
        if now - self.last_update >= 1.0:
            velocity = (files - self.last_files) * 60
            self.last_files = files
            self.last_update = now
        else:
            velocity = 0
        
        # Progress bar
        total = self.stats.get("files_found", 0) or 1
        progress = files / total
        bar_width = 20
        filled = int(progress * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)
        
        # Current file (truncated)
        short_file = current_file[-40:] if len(current_file) > 40 else current_file
        
        # Print
        print(
            f"\r[{bar}] {progress*100:>5.1f}% | "
            f"{files:>6,} files | "
            f"{self.stats.get('chunks_created', 0):>8,} chunks | "
            f"{velocity:>4.0f}/min | "
            f"{short_file:<40}",
            end="",
            flush=True
        )


def create_dashboard(stats: dict, minimal: bool = False):
    """Factory function to create appropriate dashboard."""
    if minimal:
        return MinimalTelemetry(stats)
    return AdvancedTelemetryDashboard(stats)
