"""
console_utils.py — Rich console helpers (logging, display)
"""

import os
import sys
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule

if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

console = Console(highlight=False, emoji=False)

def step(label):  console.print(f"\n[bold cyan]{label}[/bold cyan]")
def ok(msg):      console.print(f"  [bold green]OK[/bold green] {msg}")
def warn(msg):    console.print(f"  [bold yellow]!![/bold yellow]  {msg}")
def err(msg):     console.print(f"  [bold red]XX[/bold red] {msg}")
def info(msg):    console.print(f"  [dim]{msg}[/dim]")
def dbg(msg):
    from modules.config import DEBUG
    if DEBUG:
        console.print(f"  [dim magenta][DBG] {msg}[/dim magenta]")

def rule(label="", style="cyan"):
    console.rule(f"[{style}]{label}[/{style}]" if label else "", style=style)

def header_panel(title, subtitle=""):
    console.print()
    console.print(Panel(
        f"[bold cyan]{title}[/bold cyan]"
        + (f"\n[dim]{subtitle}[/dim]" if subtitle else ""),
        border_style="cyan", padding=(0, 2), expand=False
    ))
    console.print()
