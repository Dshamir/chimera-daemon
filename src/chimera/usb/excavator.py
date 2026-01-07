"""CHIMERA USB Excavator - Main entry point.

Plug USB → Admin auth → Select drive → Excavate → Save to USB

Supports:
- Text/Documents: Full chunking + entity extraction
- Images: EXIF + GPS + thumbnails (AI analysis on server)
- Audio: Register only (transcription on demand)
"""

import asyncio
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.prompt import Prompt, Confirm
    from rich.live import Live
except ImportError:
    print("Installing dependencies...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "rich", "-q"])
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.prompt import Prompt, Confirm
    from rich.live import Live

console = Console()

# ASCII Banner
BANNER = """
[bold cyan]   ██████╗██╗  ██╗██╗███╗   ███╗███████╗██████╗  █████╗[/bold cyan]
[bold cyan]  ██╔════╝██║  ██║██║████╗ ████║██╔════╝██╔══██╗██╔══██╗[/bold cyan]
[bold cyan]  ██║     ███████║██║██╔████╔██║█████╗  ██████╔╝███████║[/bold cyan]
[bold cyan]  ██║     ██╔══██║██║██║╚██╔╝██║██╔══╝  ██╔══██╗██╔══██║[/bold cyan]
[bold cyan]  ╚██████╗██║  ██║██║██║ ╚═╝ ██║███████╗██║  ██║██║  ██║[/bold cyan]
[bold cyan]   ╚═════╝╚═╝  ╚═╝╚═╝╚═╝     ╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝[/bold cyan]
[bold yellow]              USB EXCAVATOR v1.1[/bold yellow]
[dim]       Portable Cognitive Archaeology System[/dim]
[dim]       📄 Documents  📷 Images  🎵 Audio[/dim]
"""


def is_wsl() -> bool:
    """Check if running in WSL."""
    return "microsoft" in platform.release().lower() or "wsl" in platform.release().lower()


# File type categories
TEXT_EXTENSIONS = {
    ".txt", ".md", ".pdf", ".docx", ".doc",
    ".py", ".js", ".ts", ".java", ".c", ".cpp", ".h",
    ".json", ".yaml", ".yml", ".xml", ".csv",
    ".html", ".css", ".sql", ".sh", ".bat", ".ps1",
    ".log", ".ini", ".cfg", ".conf", ".rst", ".tex",
}

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp",
    ".bmp", ".tiff", ".tif", ".heic", ".heif",
}

AUDIO_EXTENSIONS = {
    ".mp3", ".wav", ".m4a", ".flac", ".ogg",
    ".aac", ".wma", ".opus", ".aiff",
}

ALL_EXTENSIONS = TEXT_EXTENSIONS | IMAGE_EXTENSIONS | AUDIO_EXTENSIONS

# Directories to skip
SKIP_DIRS = {
    'node_modules', '__pycache__', '.git', 'venv', 'env', '.venv',
    'Windows', 'Program Files', 'Program Files (x86)',
    '$Recycle.Bin', 'System Volume Information',
    '.cache', '.local', '.config', 'snap',
    'AppData', 'ProgramData', '.npm', '.yarn',
    'site-packages', 'dist-packages',
}


class USBExcavator:
    """Portable excavation system for USB deployment."""
    
    def __init__(self):
        self.os_type = platform.system()
        self.is_wsl = is_wsl()
        self.machine_id = self._get_machine_id()
        self.usb_root = self._find_usb_root()
        self.excavation_dir = None
        self.stats = {
            "files_found": 0,
            "files_processed": 0,
            "chunks_created": 0,
            "entities_extracted": 0,
            "images_processed": 0,
            "audio_registered": 0,
            "errors": 0,
            "start_time": None,
            "end_time": None,
        }
        self.entity_counts = {
            "EMAIL": 0, "URL": 0, "PATH": 0, "DATE": 0,
            "PROPER_NOUN": 0, "GPS": 0, "CAMERA": 0,
        }
    
    def _get_machine_id(self) -> str:
        """Generate unique machine identifier."""
        import socket
        hostname = socket.gethostname()
        machine_hash = hashlib.md5(hostname.encode()).hexdigest()[:8]
        return f"{hostname}-{machine_hash}"
    
    def _find_usb_root(self) -> Path:
        """Find the USB drive root."""
        script_path = Path(__file__).resolve()
        current = script_path.parent
        for _ in range(10):
            marker = current / ".chimera-usb"
            if marker.exists():
                return current
            if current.parent == current:
                break
            current = current.parent
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
        """Request admin elevation - WSL aware."""
        if self.check_admin():
            return True
        console.print("[yellow]⚠ Admin privileges required for full drive access[/yellow]")
        if self.is_wsl:
            console.print("[dim]WSL detected - continuing with user permissions[/dim]")
            return False
        elif self.os_type == "Windows":
            import ctypes
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, " ".join(sys.argv), None, 1
            )
            sys.exit(0)
        else:
            console.print("[red]Please run with sudo[/red]")
            sys.exit(1)
    
    def get_drives(self) -> List[Dict]:
        """Get list of available drives - WSL aware."""
        drives = []
        import shutil
        
        if self.os_type == "Windows":
            import string
            from ctypes import windll
            bitmask = windll.kernel32.GetLogicalDrives()
            for letter in string.ascii_uppercase:
                if bitmask & 1:
                    drive_path = f"{letter}:\\"
                    try:
                        total, used, free = shutil.disk_usage(drive_path)
                        drive_type = windll.kernel32.GetDriveTypeW(drive_path)
                        type_names = {0: "Unknown", 1: "No Root", 2: "Removable",
                                      3: "Fixed", 4: "Network", 5: "CD-ROM", 6: "RAM Disk"}
                        drives.append({
                            "path": drive_path, "letter": letter,
                            "total_gb": total / (1024**3), "free_gb": free / (1024**3),
                            "type": type_names.get(drive_type, "Unknown"),
                        })
                    except:
                        pass
                bitmask >>= 1
        elif self.is_wsl:
            mnt_path = Path("/mnt")
            if mnt_path.exists():
                for item in mnt_path.iterdir():
                    if item.is_dir() and len(item.name) == 1 and item.name.isalpha():
                        try:
                            total, used, free = shutil.disk_usage(str(item))
                            drives.append({
                                "path": str(item), "letter": item.name.upper(),
                                "total_gb": total / (1024**3), "free_gb": free / (1024**3),
                                "type": "Windows",
                            })
                        except:
                            pass
            try:
                total, used, free = shutil.disk_usage("/")
                drives.append({"path": "/", "letter": "/", "total_gb": total / (1024**3),
                               "free_gb": free / (1024**3), "type": "Linux Root"})
            except:
                pass
        else:
            for mp in ["/", "/home", "/mnt", "/media"]:
                if os.path.exists(mp):
                    try:
                        total, used, free = shutil.disk_usage(mp)
                        drives.append({"path": mp, "letter": mp, "total_gb": total / (1024**3),
                                       "free_gb": free / (1024**3), "type": "Fixed"})
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
        table.add_column("Drive", width=20)
        table.add_column("Size", width=12)
        table.add_column("Free", width=12)
        table.add_column("Type", width=12)
        
        for i, drive in enumerate(drives, 1):
            table.add_row(str(i), drive["path"], f"{drive['total_gb']:.1f} GB",
                          f"{drive['free_gb']:.1f} GB", drive["type"])
        table.add_row(str(len(drives) + 1), "* ALL *", "-", "-", "Multiple")
        table.add_row(str(len(drives) + 2), "[Custom Path]", "-", "-", "Manual")
        console.print(table)
        
        choice = Prompt.ask("\nSelect drive (or enter path)", default="1")
        if choice.startswith("/") or (len(choice) > 1 and choice[1] == ":"):
            custom_path = Path(choice)
            return custom_path if custom_path.exists() else None
        
        try:
            idx = int(choice) - 1
            if idx == len(drives):
                return "ALL"
            if idx == len(drives) + 1:
                custom = Prompt.ask("Enter path")
                custom_path = Path(custom)
                return custom_path if custom_path.exists() else None
            if 0 <= idx < len(drives):
                return Path(drives[idx]["path"])
        except:
            pass
        return None
    
    def setup_excavation_dir(self) -> Path:
        """Create excavation output directory."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        excavation_name = f"{self.machine_id}_{timestamp}"
        self.excavation_dir = self.usb_root / "excavations" / excavation_name
        self.excavation_dir.mkdir(parents=True, exist_ok=True)
        for subdir in ["chunks", "entities", "images", "audio", "metadata"]:
            (self.excavation_dir / subdir).mkdir(exist_ok=True)
        return self.excavation_dir
    
    def save_metadata(self):
        """Save excavation metadata."""
        metadata = {
            "machine_id": self.machine_id,
            "os": self.os_type,
            "os_version": platform.version(),
            "hostname": platform.node(),
            "is_wsl": self.is_wsl,
            "excavation_start": self.stats["start_time"].isoformat() if self.stats["start_time"] else None,
            "excavation_end": self.stats["end_time"].isoformat() if self.stats["end_time"] else None,
            "stats": self.stats.copy(),
            "entity_breakdown": self.entity_counts,
        }
        metadata["stats"].pop("start_time", None)
        metadata["stats"].pop("end_time", None)
        with open(self.excavation_dir / "metadata" / "excavation.json", "w") as f:
            json.dump(metadata, f, indent=2)
    
    async def run(self):
        """Main excavation flow."""
        console.clear()
        console.print(BANNER)
        
        console.print("\n[bold]SYSTEM CHECK[/bold]")
        console.print(f"  OS: {self.os_type} {platform.release()}")
        if self.is_wsl:
            console.print(f"  Environment: [cyan]WSL[/cyan]")
        console.print(f"  Machine: {self.machine_id}")
        console.print(f"  USB Root: {self.usb_root}")
        
        if not self.check_admin():
            if self.is_wsl:
                console.print("  Admin: [yellow]○[/yellow] (user mode)")
            elif Confirm.ask("\n[yellow]Request admin privileges?[/yellow]"):
                self.request_admin()
        else:
            console.print("  Admin: [green]✓[/green]")
        
        target = self.select_target_drive()
        if not target:
            return
        
        self.setup_excavation_dir()
        console.print(f"\n[green]✓[/green] Output: {self.excavation_dir}")
        
        if not Confirm.ask("\n[bold]Start excavation?[/bold]"):
            console.print("[yellow]Cancelled[/yellow]")
            return
        
        self.stats["start_time"] = datetime.now()
        
        if target == "ALL":
            for drive in self.get_drives():
                await self.excavate_drive(Path(drive["path"]))
        else:
            await self.excavate_drive(target)
        
        self.stats["end_time"] = datetime.now()
        self.save_metadata()
        
        duration = (self.stats["end_time"] - self.stats["start_time"]).total_seconds()
        console.print("\n")
        console.print(Panel.fit(
            f"[bold green]EXCAVATION COMPLETE[/bold green]\n\n"
            f"  📄 Text files: {self.stats['files_processed']:,}\n"
            f"  📷 Images: {self.stats['images_processed']:,}\n"
            f"  🎵 Audio: {self.stats['audio_registered']:,}\n"
            f"  🧩 Chunks: {self.stats['chunks_created']:,}\n"
            f"  🏷️ Entities: {self.stats['entities_extracted']:,}\n"
            f"  ❌ Errors: {self.stats['errors']}\n"
            f"  ⏱️ Duration: {duration:.1f}s\n\n"
            f"  Output: {self.excavation_dir}",
            border_style="green"
        ))
        console.print("\n[dim]Sync with server: chimera /sync[/dim]")
    
    async def excavate_drive(self, drive_path: Path):
        """Excavate a single drive."""
        from chimera.usb.telemetry import TelemetryDashboard
        
        console.print(f"\n[bold]Excavating: {drive_path}[/bold]")
        dashboard = TelemetryDashboard(self.stats, self.entity_counts)
        
        with Live(dashboard.get_layout(), refresh_per_second=4, console=console) as live:
            for root, dirs, files in os.walk(drive_path):
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in SKIP_DIRS]
                
                for filename in files:
                    file_path = Path(root) / filename
                    ext = file_path.suffix.lower()
                    
                    if ext not in ALL_EXTENSIONS:
                        continue
                    
                    self.stats["files_found"] += 1
                    dashboard.current_file = str(file_path)
                    
                    try:
                        if ext in IMAGE_EXTENSIONS:
                            result = await self.process_image(file_path)
                            if result:
                                self.stats["images_processed"] += 1
                                dashboard.add_to_feed(f"📷 {file_path.name}")
                        elif ext in AUDIO_EXTENSIONS:
                            result = await self.process_audio(file_path)
                            if result:
                                self.stats["audio_registered"] += 1
                                dashboard.add_to_feed(f"🎵 {file_path.name}")
                        else:
                            result = await self.process_text(file_path)
                            if result:
                                self.stats["files_processed"] += 1
                                self.stats["chunks_created"] += result.get("chunks", 0)
                                self.stats["entities_extracted"] += result.get("entities", 0)
                                dashboard.add_to_feed(f"📄 {file_path.name}")
                    except PermissionError:
                        self.stats["errors"] += 1
                        dashboard.add_to_feed(f"⊘ {file_path.name}")
                    except Exception as e:
                        self.stats["errors"] += 1
                        dashboard.add_to_feed(f"✗ {file_path.name}")
                    
                    live.update(dashboard.get_layout())
    
    async def process_image(self, file_path: Path) -> Optional[Dict]:
        """Process image - extract EXIF, GPS, generate thumbnail."""
        try:
            from chimera.extractors.image import ImageExtractor
            extractor = ImageExtractor(generate_thumbnails=True, geocode=True)
            result = await extractor.extract(file_path)
            
            # Update entity counts
            if result.get("gps"):
                self.entity_counts["GPS"] += 1
                self.stats["entities_extracted"] += 1
            if result.get("exif", {}).get("camera"):
                self.entity_counts["CAMERA"] += 1
                self.stats["entities_extracted"] += 1
            
            # Save result
            file_id = result.get("id", hashlib.md5(str(file_path).encode()).hexdigest()[:12])
            output_file = self.excavation_dir / "images" / f"{file_id}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, default=str)
            
            return result
        except ImportError:
            # Fallback: basic metadata only
            return await self._process_image_basic(file_path)
        except Exception:
            return None
    
    async def _process_image_basic(self, file_path: Path) -> Optional[Dict]:
        """Basic image processing without full extractor."""
        try:
            file_hash = hashlib.md5(str(file_path).encode()).hexdigest()[:12]
            result = {
                "id": f"img_{file_hash}",
                "file_path": str(file_path),
                "file_name": file_path.name,
                "file_type": "image",
                "extension": file_path.suffix.lower(),
                "file_size": file_path.stat().st_size,
                "needs_ai_analysis": True,
                "extracted_at": datetime.now().isoformat(),
            }
            
            output_file = self.excavation_dir / "images" / f"img_{file_hash}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)
            
            return result
        except:
            return None
    
    async def process_audio(self, file_path: Path) -> Optional[Dict]:
        """Process audio - register only, no transcription."""
        try:
            from chimera.extractors.audio import AudioExtractor
            extractor = AudioExtractor()
            result = await extractor.extract_fast(file_path)
            
            file_id = result.get("id", hashlib.md5(str(file_path).encode()).hexdigest()[:12])
            output_file = self.excavation_dir / "audio" / f"{file_id}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, default=str)
            
            return result
        except ImportError:
            return await self._process_audio_basic(file_path)
        except Exception:
            return None
    
    async def _process_audio_basic(self, file_path: Path) -> Optional[Dict]:
        """Basic audio registration without full extractor."""
        try:
            file_hash = hashlib.md5(str(file_path).encode()).hexdigest()[:12]
            result = {
                "id": f"aud_{file_hash}",
                "file_path": str(file_path),
                "file_name": file_path.name,
                "file_type": "audio",
                "extension": file_path.suffix.lower(),
                "file_size": file_path.stat().st_size,
                "needs_transcription": True,
                "extracted_at": datetime.now().isoformat(),
            }
            
            output_file = self.excavation_dir / "audio" / f"aud_{file_hash}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)
            
            return result
        except:
            return None
    
    async def process_text(self, file_path: Path) -> Optional[Dict]:
        """Process text file - chunk and extract entities."""
        try:
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
            except:
                return None
            
            if not content.strip():
                return None
            
            chunks = self._chunk_text(content)
            entities = self._extract_entities(content)
            
            # Update entity counts
            for entity in entities:
                etype = entity.get("type", "OTHER")
                if etype in self.entity_counts:
                    self.entity_counts[etype] += 1
            
            file_id = hashlib.md5(str(file_path).encode()).hexdigest()[:12]
            
            # Save chunks
            chunk_data = {
                "file_id": file_id,
                "file_path": str(file_path),
                "file_name": file_path.name,
                "chunks": chunks,
                "chunk_count": len(chunks),
            }
            with open(self.excavation_dir / "chunks" / f"{file_id}.json", "w", encoding="utf-8") as f:
                json.dump(chunk_data, f)
            
            # Save entities
            if entities:
                entity_data = {
                    "file_id": file_id,
                    "file_path": str(file_path),
                    "entities": entities,
                }
                with open(self.excavation_dir / "entities" / f"{file_id}.json", "w", encoding="utf-8") as f:
                    json.dump(entity_data, f)
            
            return {"chunks": len(chunks), "entities": len(entities)}
        except:
            return None
    
    def _chunk_text(self, content: str, chunk_size: int = 1000) -> List[Dict]:
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
    
    def _extract_entities(self, content: str) -> List[Dict]:
        """Pattern-based entity extraction."""
        entities = []
        
        # Emails
        for match in re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', content)[:10]:
            entities.append({"type": "EMAIL", "value": match})
        
        # URLs
        for match in re.findall(r'https?://[^\s<>"]+', content)[:10]:
            entities.append({"type": "URL", "value": match})
        
        # Paths
        for match in re.findall(r'[A-Z]:\\[\w\\.-]+|/[\w/.-]+', content)[:10]:
            entities.append({"type": "PATH", "value": match})
        
        # Dates
        for match in re.findall(r'\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}', content)[:10]:
            entities.append({"type": "DATE", "value": match})
        
        # Proper nouns
        for match in re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b', content)[:20]:
            entities.append({"type": "PROPER_NOUN", "value": match})
        
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
