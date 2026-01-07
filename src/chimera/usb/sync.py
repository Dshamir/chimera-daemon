"""Sync excavations from USB to central server.

Merges portable excavations into master catalog for GPU-accelerated correlation.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

console = Console()


class ExcavationSync:
    """Sync USB excavations to central server."""
    
    def __init__(self, server_data_dir: Optional[Path] = None):
        from chimera.config import DEFAULT_CONFIG_DIR
        self.server_data_dir = server_data_dir or DEFAULT_CONFIG_DIR
        self.sync_log = self.server_data_dir / "sync_log.jsonl"
    
    def find_usb_excavations(self) -> list[Path]:
        """Find all USB drives with excavation data."""
        excavations = []
        
        import platform
        if platform.system() == "Windows":
            import string
            from ctypes import windll
            
            bitmask = windll.kernel32.GetLogicalDrives()
            for letter in string.ascii_uppercase:
                if bitmask & 1:
                    drive_path = Path(f"{letter}:\\")
                    marker = drive_path / ".chimera-usb"
                    exc_dir = drive_path / "excavations"
                    
                    if marker.exists() and exc_dir.exists():
                        # Find all excavation folders
                        for exc in exc_dir.iterdir():
                            if exc.is_dir() and (exc / "metadata" / "excavation.json").exists():
                                excavations.append(exc)
                bitmask >>= 1
        else:
            # Linux/Mac - check /mnt, /media, /Volumes
            for mount_base in ["/mnt", "/media", "/Volumes"]:
                mount_path = Path(mount_base)
                if mount_path.exists():
                    for drive in mount_path.iterdir():
                        marker = drive / ".chimera-usb"
                        exc_dir = drive / "excavations"
                        
                        if marker.exists() and exc_dir.exists():
                            for exc in exc_dir.iterdir():
                                if exc.is_dir() and (exc / "metadata" / "excavation.json").exists():
                                    excavations.append(exc)
        
        return excavations
    
    def get_excavation_info(self, exc_path: Path) -> dict:
        """Get info about an excavation."""
        metadata_file = exc_path / "metadata" / "excavation.json"
        
        if metadata_file.exists():
            with open(metadata_file) as f:
                return json.load(f)
        
        return {
            "machine_id": exc_path.name,
            "stats": {"files_processed": 0, "chunks_created": 0, "entities_extracted": 0},
        }
    
    def is_synced(self, exc_path: Path) -> bool:
        """Check if excavation was already synced."""
        if not self.sync_log.exists():
            return False
        
        exc_id = exc_path.name
        
        with open(self.sync_log) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    if entry.get("excavation_id") == exc_id and entry.get("status") == "completed":
                        return True
                except:
                    pass
        
        return False
    
    def log_sync(self, exc_path: Path, status: str, stats: dict):
        """Log sync operation."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "excavation_id": exc_path.name,
            "excavation_path": str(exc_path),
            "status": status,
            "stats": stats,
        }
        
        with open(self.sync_log, "a") as f:
            f.write(json.dumps(entry) + "\n")
    
    async def sync_excavation(self, exc_path: Path) -> dict:
        """Sync a single excavation to server."""
        from chimera.storage.catalog import CatalogDB, FileRecord, ChunkRecord, EntityRecord
        from chimera.utils.hashing import generate_id
        
        catalog = CatalogDB()
        stats = {"files": 0, "chunks": 0, "entities": 0, "errors": 0}
        
        # Process chunks
        chunks_dir = exc_path / "chunks"
        if chunks_dir.exists():
            for chunk_file in chunks_dir.glob("*.json"):
                try:
                    with open(chunk_file) as f:
                        data = json.load(f)
                    
                    file_id = data.get("file_id")
                    file_path = data.get("file_path")
                    
                    # Create file record
                    file_record = FileRecord(
                        id=file_id,
                        path=file_path,
                        filename=data.get("file_name", Path(file_path).name),
                        extension=Path(file_path).suffix.lstrip(".").lower(),
                        status="synced",
                        indexed_at=datetime.now(),
                    )
                    
                    try:
                        catalog.add_file(file_record)
                        stats["files"] += 1
                    except:
                        pass  # File might already exist
                    
                    # Create chunk records
                    chunk_records = []
                    for chunk in data.get("chunks", []):
                        chunk_id = generate_id("chunk", f"{file_id}_{chunk['index']}")
                        chunk_records.append(ChunkRecord(
                            id=chunk_id,
                            file_id=file_id,
                            chunk_index=chunk["index"],
                            content=chunk["content"],
                            chunk_type="paragraph",
                        ))
                    
                    if chunk_records:
                        try:
                            catalog.add_chunks(chunk_records)
                            stats["chunks"] += len(chunk_records)
                        except:
                            stats["errors"] += 1
                
                except Exception as e:
                    stats["errors"] += 1
        
        # Process entities
        entities_dir = exc_path / "entities"
        if entities_dir.exists():
            for entity_file in entities_dir.glob("*.json"):
                try:
                    with open(entity_file) as f:
                        data = json.load(f)
                    
                    file_id = data.get("file_id")
                    
                    entity_records = []
                    for i, entity in enumerate(data.get("entities", [])):
                        entity_id = generate_id("ent", f"{file_id}_{i}")
                        entity_records.append(EntityRecord(
                            id=entity_id,
                            file_id=file_id,
                            entity_type=entity.get("type", "UNKNOWN"),
                            value=entity.get("value", ""),
                            normalized=entity.get("value", "").lower(),
                            confidence=0.8,
                        ))
                    
                    if entity_records:
                        try:
                            catalog.add_entities(entity_records)
                            stats["entities"] += len(entity_records)
                        except:
                            stats["errors"] += 1
                
                except Exception as e:
                    stats["errors"] += 1
        
        return stats
    
    async def sync_all(self):
        """Find and sync all USB excavations."""
        console.print("\n[bold]CHIMERA SYNC[/bold]")
        console.print("[dim]Scanning for USB excavations...[/dim]\n")
        
        excavations = self.find_usb_excavations()
        
        if not excavations:
            console.print("[yellow]No USB excavations found.[/yellow]")
            console.print("[dim]Make sure USB drive with .chimera-usb marker is connected.[/dim]")
            return
        
        # Show found excavations
        table = Table(title="Found Excavations")
        table.add_column("Status", width=8)
        table.add_column("Machine ID", width=30)
        table.add_column("Files", justify="right", width=10)
        table.add_column("Chunks", justify="right", width=10)
        table.add_column("Entities", justify="right", width=10)
        
        to_sync = []
        
        for exc in excavations:
            info = self.get_excavation_info(exc)
            synced = self.is_synced(exc)
            stats = info.get("stats", {})
            
            status = "[green]✓ Synced[/green]" if synced else "[yellow]○ New[/yellow]"
            
            table.add_row(
                status,
                info.get("machine_id", exc.name),
                str(stats.get("files_processed", 0)),
                str(stats.get("chunks_created", 0)),
                str(stats.get("entities_extracted", 0)),
            )
            
            if not synced:
                to_sync.append(exc)
        
        console.print(table)
        
        if not to_sync:
            console.print("\n[green]All excavations already synced.[/green]")
            return
        
        console.print(f"\n[bold]{len(to_sync)} new excavation(s) to sync[/bold]")
        
        # Sync each new excavation
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            
            task = progress.add_task("Syncing...", total=len(to_sync))
            
            total_stats = {"files": 0, "chunks": 0, "entities": 0, "errors": 0}
            
            for exc in to_sync:
                info = self.get_excavation_info(exc)
                progress.update(task, description=f"Syncing {info.get('machine_id', exc.name)}...")
                
                try:
                    stats = await self.sync_excavation(exc)
                    
                    for key in total_stats:
                        total_stats[key] += stats.get(key, 0)
                    
                    self.log_sync(exc, "completed", stats)
                    
                except Exception as e:
                    self.log_sync(exc, "failed", {"error": str(e)})
                    console.print(f"[red]Error syncing {exc.name}: {e}[/red]")
                
                progress.update(task, advance=1)
        
        # Summary
        console.print("\n")
        console.print(Panel.fit(
            f"[bold green]SYNC COMPLETE[/bold green]\n\n"
            f"  Files added: {total_stats['files']:,}\n"
            f"  Chunks added: {total_stats['chunks']:,}\n"
            f"  Entities added: {total_stats['entities']:,}\n"
            f"  Errors: {total_stats['errors']}",
            border_style="green"
        ))
        
        console.print("\n[dim]Run /correlate --gpu to analyze with GPU acceleration[/dim]")


async def sync_command():
    """CLI command for syncing."""
    sync = ExcavationSync()
    await sync.sync_all()
