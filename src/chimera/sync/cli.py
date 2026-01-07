"""CLI commands for cross-machine sync."""

import asyncio
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


async def cmd_sync(usb_path: Optional[str] = None):
    """Sync USB excavations to server."""
    from chimera.usb.sync import ExcavationSync
    
    sync = ExcavationSync()
    await sync.sync_all()


async def cmd_merge(excavations_path: str):
    """Merge all excavations in a directory."""
    from chimera.sync.merger import CatalogMerger
    
    console.print(f"[yellow]Merging excavations from {excavations_path}...[/yellow]")
    
    merger = CatalogMerger()
    result = await merger.merge_all(Path(excavations_path))
    
    console.print(Panel.fit(
        f"[bold green]MERGE COMPLETE[/bold green]\n\n"
        f"  Machines: {', '.join(result.machines_merged)}\n"
        f"  Files added: {result.files_added:,}\n"
        f"  Files deduplicated: {result.files_deduplicated:,}\n"
        f"  Chunks added: {result.chunks_added:,}\n"
        f"  Entities added: {result.entities_added:,}\n"
        f"  Entities consolidated: {result.entities_consolidated:,}\n"
        f"  Errors: {len(result.errors)}",
        border_style="green"
    ))
    
    if result.errors:
        console.print("\n[red]Errors:[/red]")
        for err in result.errors[:10]:
            console.print(f"  [dim]{err}[/dim]")


async def cmd_discover():
    """Run cross-machine discovery analysis."""
    from chimera.sync.discovery import CrossMachineDiscovery
    
    console.print("[yellow]🔍 Running cross-machine discovery...[/yellow]")
    
    discovery = CrossMachineDiscovery()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Analyzing patterns...", total=None)
        patterns, insights = await discovery.analyze()
        progress.update(task, description="Complete!")
    
    # Display patterns
    if patterns:
        console.print(f"\n[bold]📊 Patterns Found ({len(patterns)})[/bold]")
        
        table = Table(show_header=True)
        table.add_column("Type", style="cyan", width=12)
        table.add_column("Name", width=30)
        table.add_column("Machines", width=20)
        table.add_column("Confidence", justify="right", width=10)
        
        for p in patterns[:15]:
            conf_color = "green" if p.confidence > 0.6 else "yellow" if p.confidence > 0.3 else "dim"
            table.add_row(
                p.pattern_type,
                p.name[:28],
                ", ".join(p.machines)[:18],
                f"[{conf_color}]{p.confidence:.0%}[/{conf_color}]",
            )
        
        console.print(table)
    
    # Display insights
    if insights:
        console.print(f"\n[bold]💡 Insights ({len(insights)})[/bold]")
        
        for insight in insights:
            console.print(Panel(
                f"[bold]{insight.title}[/bold]\n\n"
                f"{insight.description}\n\n"
                f"[dim]Recommendations:[/dim]\n" +
                "\n".join(f"  • {r}" for r in insight.recommendations),
                border_style="yellow" if insight.insight_type == "gap" else "green",
            ))
    
    # Summary
    summary = discovery.get_summary()
    console.print(f"\n[dim]Summary: {summary['machines_analyzed']} machines, "
                 f"{summary['total_entities']} entities, "
                 f"{summary['patterns_found']} patterns[/dim]")


async def cmd_history(limit: int = 20):
    """Show merge history."""
    from chimera.sync.merger import CatalogMerger
    
    merger = CatalogMerger()
    history = merger.get_merge_history(limit)
    
    if not history:
        console.print("[yellow]No merge history found[/yellow]")
        return
    
    table = Table(title="Merge History")
    table.add_column("Date", width=20)
    table.add_column("Machines", width=30)
    table.add_column("Files", justify="right")
    table.add_column("Entities", justify="right")
    
    for entry in reversed(history):
        table.add_row(
            entry.get("timestamp", "")[:19],
            ", ".join(entry.get("machines_merged", []))[:28],
            str(entry.get("files_added", 0)),
            str(entry.get("entities_added", 0)),
        )
    
    console.print(table)


def main():
    """CLI entry point."""
    import sys
    
    if len(sys.argv) < 2:
        console.print("Usage: python -m chimera.sync.cli <command>")
        console.print("Commands: sync, merge, discover, history")
        return
    
    cmd = sys.argv[1]
    
    if cmd == "sync":
        usb_path = sys.argv[2] if len(sys.argv) > 2 else None
        asyncio.run(cmd_sync(usb_path))
    elif cmd == "merge":
        if len(sys.argv) < 3:
            console.print("Usage: python -m chimera.sync.cli merge <path>")
            return
        asyncio.run(cmd_merge(sys.argv[2]))
    elif cmd == "discover":
        asyncio.run(cmd_discover())
    elif cmd == "history":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        asyncio.run(cmd_history(limit))
    else:
        console.print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
