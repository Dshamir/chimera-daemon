"""File system watcher for CHIMERA.

Monitors configured directories for changes and queues
extraction jobs.
"""

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from chimera.config import ChimeraConfig, SourceConfig
from chimera.utils.logging import get_logger

logger = get_logger(__name__)


class ChimeraEventHandler(FileSystemEventHandler):
    """Handle file system events for CHIMERA."""
    
    def __init__(
        self,
        source: SourceConfig,
        on_change: Callable[[Path, str], None],
        exclude_patterns: list[str],
    ) -> None:
        self.source = source
        self.on_change = on_change
        self.exclude_patterns = exclude_patterns
        self._debounce_lock = threading.Lock()
        self._recent_events: dict[str, float] = {}
        self._debounce_seconds = 2.0
        
    def _should_ignore(self, path: str) -> bool:
        """Check if path should be ignored."""
        from fnmatch import fnmatch
        
        path_lower = path.lower()
        
        # Always ignore hidden files
        if Path(path).name.startswith("."):
            return True
        
        for pattern in self.exclude_patterns:
            if fnmatch(path_lower, pattern.lower()):
                return True
            # Also check just the filename
            if fnmatch(Path(path).name.lower(), pattern.lower()):
                return True
        
        return False
    
    def _get_extension(self, path: str) -> str:
        """Get file extension without dot."""
        return Path(path).suffix.lstrip(".").lower()
    
    def _is_within_depth(self, path: str) -> bool:
        """Check if path is within allowed depth from source root.

        Args:
            path: Full path to the file

        Returns:
            True if within allowed depth, or if max_depth is None (unlimited)
        """
        if self.source.max_depth is None:
            return True  # Unlimited depth

        try:
            source_path = Path(self.source.path).resolve()
            file_path = Path(path).resolve()

            # Get relative path from source
            relative = file_path.relative_to(source_path)
            depth = len(relative.parts) - 1  # Subtract 1 because file itself is not a level

            return depth <= self.source.max_depth
        except ValueError:
            # Path is not under source_path
            return False

    def _should_process(self, path: str) -> bool:
        """Check if file should be processed."""
        if self._should_ignore(path):
            return False

        # Check depth limit
        if not self._is_within_depth(path):
            return False

        # Check file type filter if specified
        if self.source.file_types:
            ext = self._get_extension(path)
            if ext not in [ft.lower() for ft in self.source.file_types]:
                return False

        return True
    
    def _is_debounced(self, path: str) -> bool:
        """Check if event should be debounced."""
        import time
        
        current_time = time.time()
        
        with self._debounce_lock:
            last_time = self._recent_events.get(path, 0)
            if current_time - last_time < self._debounce_seconds:
                return True
            self._recent_events[path] = current_time
            
            # Clean old entries
            cutoff = current_time - self._debounce_seconds * 2
            self._recent_events = {
                k: v for k, v in self._recent_events.items()
                if v > cutoff
            }
        
        return False
    
    def _handle_event(self, path: str, event_type: str) -> None:
        """Handle a file event."""
        if not self._should_process(path):
            return
        
        if self._is_debounced(path):
            return
        
        self.on_change(Path(path), event_type)
    
    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation."""
        if event.is_directory:
            return
        self._handle_event(event.src_path, "created")
    
    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification."""
        if event.is_directory:
            return
        self._handle_event(event.src_path, "modified")
    
    def on_deleted(self, event: FileSystemEvent) -> None:
        """Handle file deletion."""
        if event.is_directory:
            return
        self._handle_event(event.src_path, "deleted")
    
    def on_moved(self, event: FileSystemEvent) -> None:
        """Handle file move/rename."""
        if event.is_directory:
            return
        self._handle_event(event.dest_path, "moved")


class FileWatcher:
    """Watch configured directories for file changes."""
    
    def __init__(self, config: ChimeraConfig) -> None:
        self.config = config
        self.observer = Observer()
        self._running = False
        self.on_file_change: Callable[[Path, str], None] | None = None
        
    def _handle_change(self, path: Path, event_type: str) -> None:
        """Handle a file change event."""
        logger.debug(f"File {event_type}: {path}")
        
        # Check for FAE trigger
        if self._is_fae_trigger(path):
            logger.info(f"FAE trigger detected: {path}")
        
        # Call registered handler
        if self.on_file_change:
            self.on_file_change(path, event_type)
    
    def _is_fae_trigger(self, path: Path) -> bool:
        """Check if file might be an AI conversation export."""
        name = path.name.lower()
        return (
            name == "conversations.json"
            or ("export" in name and path.suffix == ".json")
            or ("chat" in name and path.suffix == ".json")
        )
    
    def start(self) -> None:
        """Start watching configured directories."""
        exclude_patterns = (
            self.config.exclude.paths + 
            self.config.exclude.patterns
        )
        
        watched_count = 0
        
        for source in self.config.sources:
            if not source.enabled:
                continue
                
            path = Path(source.path).expanduser()
            
            # Handle Windows paths
            if not path.exists():
                # Try without expanding for Windows drives like E:\
                path = Path(source.path)
            
            if not path.exists():
                logger.warning(f"Watch path does not exist: {source.path}")
                continue
            
            handler = ChimeraEventHandler(
                source=source,
                on_change=self._handle_change,
                exclude_patterns=exclude_patterns,
            )
            
            try:
                self.observer.schedule(
                    handler,
                    str(path),
                    recursive=source.recursive,
                )
                logger.info(f"Watching: {path} (recursive={source.recursive})")
                watched_count += 1
            except Exception as e:
                logger.error(f"Failed to watch {path}: {e}")
        
        if watched_count > 0:
            self.observer.start()
            self._running = True
            logger.info(f"File watcher started. Watching {watched_count} source(s).")
        else:
            logger.warning("No valid sources to watch.")
    
    def stop(self) -> None:
        """Stop watching."""
        if self._running:
            self.observer.stop()
            self.observer.join(timeout=5)
            self._running = False
            logger.info("File watcher stopped.")
    
    @property
    def is_running(self) -> bool:
        """Check if watcher is running."""
        return self._running
