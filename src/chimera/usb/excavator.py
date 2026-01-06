"""CHIMERA USB Excavator - Main entry point.

Plug USB → Admin auth → Select drive → Excavate → Save to USB
"""

import asyncio
import getpass
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from rich.prompt import Prompt, Confirm
    from rich.live import Live
    from rich.layout import Layout
    from rich.text import Text
except ImportError:
    print("Installing dependencies...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "rich", "-q"])
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from rich.prompt import Prompt, Confirm
    from rich.live import Live
    from rich.layout import Layout
    from rich.text import Text

console = Console()

# ASCII Banner
BANNER = """
[bold cyan]   ██████╗██╗  ██╗██╗███╗   ███╗███████╗██████╗  █████╗[/bold cyan]
[bold cyan]  ██╔════╝██║  ██║██║████╗ ████║██╔════╝██╔══██╗██╔══██╗[/bold cyan]
[bold cyan]  ██║     ███████║██║██╔████╔██║█████╗  ██████╔╝███████║[/bold cyan]
[bold cyan]  ██║     ██╔══██║██║██║╚██╔╝██║██╔══╝  ██╔══██╗██╔══██║[/bold cyan]
[bold cyan]  ╚██████╗██║  ██║██║██║ ╚═╝ ██║███████╗██║  ██║██║  ██║[/bold cyan]
[bold cyan]   ╚═════╝╚═╝  ╚═╝╚═╝╚═╝     ╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝[/bold cyan]
[bold yellow]              USB EXCAVATOR v1.0[/bold yellow]
[dim]       Portable Cognitive Archaeology System[/dim]
"""


class USBExcavator:
    """Portable excavation system for USB deployment."""
    
    def __init__(self):
        self.os_type = platform.system()  # Windows, Linux, Darwin
        self.machine_id = self._get_machine_id()
        self.usb_root = self._find_usb_root()
        self.excavation_dir = None
        self.stats = {
            "files_found": 0,
            "files_processed": 0,
            "chunks_created": 0,
            "entities_extracted": 0,
            "errors": 0,
            "start_time": None,
            "end_time": None,
        }
    
    def _get_machine_id(self) -> str:
        """Generate unique machine identifier."""
        import socket
        hostname = socket.gethostname()
        # Create short hash for uniqueness
        machine_hash = hashlib.md5(hostname.encode()).hexdigest()[:8]
        return f"{hostname}-{machine_hash}"
    
    def _find_usb_root(self) -> Path:
        """Find the USB drive root (where this script lives)."""
        # The script should be on the USB drive
        script_path = Path(__file__).resolve()
        
        # Walk up to find CHIMERA-USB marker or use script's drive
        current = script_path.parent
        for _ in range(10):  # Max depth
            marker = current / ".chimera-usb"
            if marker.exists():
                return current
            if current.parent == current:  # Root
                break
            current = current.parent
        
        # Fallback: use script's drive root
        if self.os_type == "Windows":
            return Path(script_path.drive + "/")
        return script_path.parent
    
    def check_admin(self) -> bool:
        """Check if running with admin/root privileges."""
        if self.os_type == "Windows":
            try:
                import ctypes
                return ctypes.windll.shell32.IsUserAnAdmin() != 0
            except:
                return False
        else:
            return os.geteuid() == 0
    
    def request_admin(self):
        """Request admin elevation."""
        if self.check_admin():
            return True
        
        console.print("[yellow]⚠ Admin privileges required for full drive access[/yellow]")
        
        if self.os_type == "Windows":
            console.print("[dim]Requesting elevation...[/dim]")
            import ctypes
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, " ".join(sys.argv), None, 1
            )
            sys.exit(0)
        else:
            console.print("[red]Please run with sudo: sudo python excavator.py[/red]")
            sys.exit(1)
    
    def get_drives(self) -> list[dict]:
        """Get list of available drives."""
        drives = []
        
        if self.os_type == "Windows":
            import string
            from ctypes import windll
            
            bitmask = windll.kernel32.GetLogicalDrives()
            for letter in string.ascii_uppercase:
                if bitmask & 1:
                    drive_path = f"{letter}:\\"
                    try:
                        # Get drive info
                        import shutil
                        total, used, free = shutil.disk_usage(drive_path)
                        
                        # Get drive type
                        drive_type = windll.kernel32.GetDriveTypeW(drive_path)
                        type_names = {
                            0: "Unknown", 1: "No Root", 2: "Removable",
                            3: "Fixed", 4: "Network", 5: "CD-ROM", 6: "RAM Disk"
                        }
                        
                        drives.append({
                            "path": drive_path,
                            "letter": letter,
                            "total_gb": total / (1024**3),
                            "free_gb": free / (1024**3),
                            "type": type_names.get(drive_type, "Unknown"),
                        })
                    except:
                        pass
                bitmask >>= 1
        else:
            # Linux/Mac - check common mount points
            mount_points = ["/", "/home", "/mnt", "/media"]
            for mp in mount_points:
                if os.path.exists(mp):
                    try:
                        import shutil
                        total, used, free = shutil.disk_usage(mp)
                        drives.append({
                            "path": mp,
                            "letter": mp,
                            "total_gb": total / (1024**3),
                            "free_gb": free / (1024**3),
                            "type": "Fixed",
                        })
                    except:
                        pass
        
        return drives
    
    def select_target_drive(self) -> Optional[Path]:
        """Interactive drive selection."""
        drives = self.get_drives()
        
        if not drives:
            console.print("[red]No drives found![/red]")
            return None
        
        console.print("\n[bold]SELECT TARGET DRIVE:[/bold]")
        
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("#", style="dim", width=4)
        table.add_column("Drive", width=10)
        table.add_column("Size", width=12)
        table.add_column("Free", width=12)
        table.add_column("Type", width=12)
        
        for i, drive in enumerate(drives, 1):
            table.add_row(
                str(i),
                drive["path"],
                f"{drive['total_gb']:.1f} GB",
                f"{drive['free_gb']:.1f} GB",
                drive["type"]
            )
        
        # Add "All Drives" option
        table.add_row(str(len(drives) + 1), "* ALL *", "-", "-", "Multiple")
        
        console.print(table)
        
        choice = Prompt.ask("\nSelect drive", default="1")
        
        try:
            idx = int(choice) - 1
            if idx == len(drives):  # All drives
                return "ALL"
            if 0 <= idx < len(drives):
                return Path(drives[idx]["path"])
        except:
            pass
        
        console.print("[red]Invalid selection[/red]")
        return None
    
    def setup_excavation_dir(self) -> Path:
        """Create excavation output directory on USB."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        excavation_name = f"{self.machine_id}_{timestamp}"
        
        self.excavation_dir = self.usb_root / "excavations" / excavation_name
        self.excavation_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (self.excavation_dir / "chunks").mkdir(exist_ok=True)
        (self.excavation_dir / "entities").mkdir(exist_ok=True)
        (self.excavation_dir / "metadata").mkdir(exist_ok=True)
        
        return self.excavation_dir
    
    def save_metadata(self):
        """Save excavation metadata."""
        metadata = {
            "machine_id": self.machine_id,
            "os": self.os_type,
            "os_version": platform.version(),
            "hostname": platform.node(),
            "excavation_start": self.stats["start_time"].isoformat() if self.stats["start_time"] else None,
            "excavation_end": self.stats["end_time"].isoformat() if self.stats["end_time"] else None,
            "stats": {
                "files_found": self.stats["files_found"],
                "files_processed": self.stats["files_processed"],
                "chunks_created": self.stats["chunks_created"],
                "entities_extracted": self.stats["entities_extracted"],
                "errors": self.stats["errors"],
            },
        }
        
        with open(self.excavation_dir / "metadata" / "excavation.json", "w") as f:
            json.dump(metadata, f, indent=2)
    
    async def run(self):
        """Main excavation flow."""
        console.clear()
        console.print(BANNER)
        
        # Step 1: Check/request admin
        console.print("\n[bold]SYSTEM CHECK[/bold]")
        console.print(f"  OS: {self.os_type} {platform.release()}")
        console.print(f"  Machine: {self.machine_id}")
        console.print(f"  USB Root: {self.usb_root}")
        
        if not self.check_admin():
            if Confirm.ask("\n[yellow]Request admin privileges?[/yellow]"):
                self.request_admin()
            else:
                console.print("[dim]Continuing with limited access...[/dim]")
        else:
            console.print("  Admin: [green]✓[/green]")
        
        # Step 2: Select target drive
        target = self.select_target_drive()
        if not target:
            return
        
        # Step 3: Setup excavation directory
        self.setup_excavation_dir()
        console.print(f"\n[green]✓[/green] Output: {self.excavation_dir}")
        
        # Step 4: Confirm and start
        if not Confirm.ask("\n[bold]Start excavation?[/bold]"):
            console.print("[yellow]Cancelled[/yellow]")
            return
        
        # Step 5: Run excavation with telemetry
        self.stats["start_time"] = datetime.now()
        
        if target == "ALL":
            drives = self.get_drives()
            for drive in drives:
                await self.excavate_drive(Path(drive["path"]))
        else:
            await self.excavate_drive(target)
        
        self.stats["end_time"] = datetime.now()
        
        # Step 6: Save metadata and summary
        self.save_metadata()
        
        # Show completion
        duration = (self.stats["end_time"] - self.stats["start_time"]).total_seconds()
        
        console.print("\n")
        console.print(Panel.fit(
            f"[bold green]EXCAVATION COMPLETE[/bold green]\n\n"
            f"  Files processed: {self.stats['files_processed']:,}\n"
            f"  Chunks created: {self.stats['chunks_created']:,}\n"
            f"  Entities found: {self.stats['entities_extracted']:,}\n"
            f"  Errors: {self.stats['errors']}\n"
            f"  Duration: {duration:.1f}s\n\n"
            f"  Output: {self.excavation_dir}",
            border_style="green"
        ))
        
        console.print("\n[dim]Safe to eject USB. Sync with server using: chimera /sync[/dim]")
    
    async def excavate_drive(self, drive_path: Path):
        """Excavate a single drive."""
        from chimera.usb.telemetry import TelemetryDashboard
        
        console.print(f"\n[bold]Excavating: {drive_path}[/bold]")
        
        # Create telemetry dashboard
        dashboard = TelemetryDashboard(self.stats)
        
        # Scan for files
        supported_extensions = {
            ".txt", ".md", ".pdf", ".docx", ".doc",
            ".py", ".js", ".ts", ".java", ".c", ".cpp", ".h",
            ".json", ".yaml", ".yml", ".xml", ".csv",
            ".html", ".css", ".sql",
        }
        
        # Start live telemetry
        with Live(dashboard.get_layout(), refresh_per_second=4, console=console) as live:
            # Walk the drive
            for root, dirs, files in os.walk(drive_path):
                # Skip system directories
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in [
                    'node_modules', '__pycache__', '.git', 'venv', 'env',
                    'Windows', 'Program Files', 'Program Files (x86)',
                    '$Recycle.Bin', 'System Volume Information'
                ]]
                
                for filename in files:
                    file_path = Path(root) / filename
                    
                    # Check extension
                    if file_path.suffix.lower() not in supported_extensions:
                        continue
                    
                    self.stats["files_found"] += 1
                    dashboard.current_file = str(file_path)
                    
                    try:
                        # Process file
                        result = await self.process_file(file_path)
                        
                        if result:
                            self.stats["files_processed"] += 1
                            self.stats["chunks_created"] += result.get("chunks", 0)
                            self.stats["entities_extracted"] += result.get("entities", 0)
                            dashboard.add_to_feed(f"✓ {file_path.name}")
                        
                    except Exception as e:
                        self.stats["errors"] += 1
                        dashboard.add_to_feed(f"✗ {file_path.name}: {str(e)[:30]}")
                    
                    # Update display
                    live.update(dashboard.get_layout())
    
    async def process_file(self, file_path: Path) -> Optional[dict]:
        """Process a single file - extract chunks and entities."""
        try:
            # Read file
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
            except:
                return None
            
            if not content.strip():
                return None
            
            # Simple chunking (will use full pipeline later)
            chunks = self._simple_chunk(content)
            
            # Simple entity extraction (placeholder)
            entities = self._simple_entities(content)
            
            # Save to excavation directory
            file_id = hashlib.md5(str(file_path).encode()).hexdigest()[:12]
            
            # Save chunks
            chunk_data = {
                "file_id": file_id,
                "file_path": str(file_path),
                "file_name": file_path.name,
                "chunks": chunks,
                "chunk_count": len(chunks),
            }
            
            chunk_file = self.excavation_dir / "chunks" / f"{file_id}.json"
            with open(chunk_file, "w", encoding="utf-8") as f:
                json.dump(chunk_data, f)
            
            # Save entities
            if entities:
                entity_data = {
                    "file_id": file_id,
                    "file_path": str(file_path),
                    "entities": entities,
                }
                
                entity_file = self.excavation_dir / "entities" / f"{file_id}.json"
                with open(entity_file, "w", encoding="utf-8") as f:
                    json.dump(entity_data, f)
            
            return {
                "chunks": len(chunks),
                "entities": len(entities),
            }
            
        except Exception as e:
            return None
    
    def _simple_chunk(self, content: str, chunk_size: int = 1000) -> list[dict]:
        """Simple text chunking."""
        chunks = []
        words = content.split()
        
        current_chunk = []
        current_size = 0
        
        for word in words:
            current_chunk.append(word)
            current_size += len(word) + 1
            
            if current_size >= chunk_size:
                chunks.append({
                    "index": len(chunks),
                    "content": " ".join(current_chunk),
                    "word_count": len(current_chunk),
                })
                current_chunk = []
                current_size = 0
        
        if current_chunk:
            chunks.append({
                "index": len(chunks),
                "content": " ".join(current_chunk),
                "word_count": len(current_chunk),
            })
        
        return chunks
    
    def _simple_entities(self, content: str) -> list[dict]:
        """Simple entity extraction (pattern-based, no spaCy needed)."""
        import re
        
        entities = []
        
        # Email pattern
        emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', content)
        for email in emails[:10]:  # Limit
            entities.append({"type": "EMAIL", "value": email})
        
        # URL pattern
        urls = re.findall(r'https?://[^\s<>"]+', content)
        for url in urls[:10]:
            entities.append({"type": "URL", "value": url})
        
        # File paths (Windows and Unix)
        paths = re.findall(r'[A-Z]:\\[\w\\.-]+|/[\w/.-]+', content)
        for path in paths[:10]:
            entities.append({"type": "PATH", "value": path})
        
        # Dates
        dates = re.findall(r'\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}', content)
        for date in dates[:10]:
            entities.append({"type": "DATE", "value": date})
        
        # Capitalized words (potential names/orgs) - simple heuristic
        caps = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b', content)
        for cap in caps[:20]:
            entities.append({"type": "PROPER_NOUN", "value": cap})
        
        return entities


def main():
    """Entry point."""
    excavator = USBExcavator()
    
    try:
        asyncio.run(excavator.run())
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted. Saving progress...[/yellow]")
        if excavator.excavation_dir:
            excavator.stats["end_time"] = datetime.now()
            excavator.save_metadata()
        console.print("[green]Progress saved.[/green]")


if __name__ == "__main__":
    main()
