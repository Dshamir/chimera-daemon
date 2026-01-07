# Add sync command to shell.py

Add this to the commands dict:
```python
"/sync": self.cmd_sync,
```

Add this method:
```python
async def cmd_sync(self, args: str):
    """Sync USB excavations to server."""
    console.print("[yellow]🔄 Scanning for USB excavations...[/yellow]")
    
    try:
        from chimera.usb.sync import ExcavationSync
        
        sync = ExcavationSync()
        await sync.sync_all()
        
    except Exception as e:
        console.print(f"[red]Sync error: {e}[/red]")
```

Update banner to show /sync command.
