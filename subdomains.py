"""Alt alan adı keşfi - subfinder."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table

from .utils import check_tool, get_tool_missing_message, run_cmd, run_cmd_stream

console = Console()


def run_subfinder(domain: str, timeout: int = 90, stream: bool = False) -> set[str]:
    """subfinder subdomain bul."""
    subdomains = set()
    path = check_tool("subfinder")
    if not path:
        return subdomains

    cmd = [path, "-d", domain, "-silent"]

    def on_line(line: str):
        if line:
            subdomains.add(line)
            console.print(f"  [dim]→[/dim] {line}")

    if stream:
        code, _ = run_cmd_stream(cmd, timeout=timeout, on_line=on_line)
    else:
        code, output = run_cmd(cmd, timeout=timeout)
        if code == 0:
            for line in output.strip().split("\n"):
                line = line.strip()
                if line:
                    subdomains.add(line)
    return subdomains


def check_alive(host: str, timeout: int = 3) -> bool:
    """Host canlı mı? (ping veya basit HTTP check)."""
    import socket
    try:
        socket.setdefaulttimeout(timeout)
        socket.create_connection((host, 80), timeout=timeout)
        return True
    except (socket.timeout, socket.error, OSError):
        try:
            socket.create_connection((host, 443), timeout=timeout)
            return True
        except (socket.timeout, socket.error, OSError):
            return False


def discover_subdomains(
    domain: str,
    use_subfinder: bool = True,
    check_live: bool = True,
    quiet: bool = False,
    fast: bool = False,
) -> tuple[set[str], set[str]]:
    """
    Alt alan adı keşfi - subfinder.
    Returns: (all_subdomains, live_subdomains)
    """
    all_subs = set()
    tools_used = []

    if not quiet:
        if check_tool("subfinder"):
            console.print("[dim]Kullanılacak: subfinder[/dim]")
        else:
            console.print(f"[yellow]⚠ subfinder {get_tool_missing_message()}[/yellow]")
            console.print("[dim]  → bash requirements/install-tools.sh[/dim]")

    stream_output = not quiet

    if use_subfinder and check_tool("subfinder"):
        tools_used.append("subfinder")
        if not quiet:
            console.print("[bold cyan]subfinder[/bold cyan] taranıyor...")
        subs = run_subfinder(domain, timeout=60 if fast else 90, stream=stream_output)
        all_subs.update(subs)
        if not quiet and subs:
            console.print(f"  [green]✓ {len(subs)} bulundu[/green]\n")

    if not tools_used and not quiet:
        console.print("[red]Hiçbir alt alan adı aracı bulunamadı. En az biri gerekli.[/red]")
        return all_subs, set()

    # Ana domain'i de ekle
    all_subs.add(domain)

    # Canlı host kontrolü - ilerleme çubuğu ile
    live_subs = set()
    if check_live and all_subs:
        subs_list = sorted(all_subs)
        total = len(subs_list)
        max_workers = 20 if fast else 10

        if not quiet:
            progress = Progress(
                SpinnerColumn(style="bold yellow"),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(bar_width=40, style="green"),
                TaskProgressColumn(),
                console=console,
            )
            task = progress.add_task("Canlı host kontrol ediliyor...", total=total)
            progress.start()

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(check_alive, sub, 2 if fast else 3): sub for sub in subs_list}
            done = 0
            for future in as_completed(futures):
                if future.result():
                    live_subs.add(futures[future])
                done += 1
                if not quiet:
                    progress.update(task, completed=done)

        if not quiet:
            progress.stop()

    return all_subs, live_subs


def print_subdomain_results(all_subs: set[str], live_subs: set[str], quiet: bool = False):
    """Subdomain sonuçlarını güzel formatla yazdır."""
    if quiet:
        return

    table = Table(title="Alt Alan Adı Keşfi", show_header=True)
    table.add_column("Alt Alan Adı", style="cyan")
    table.add_column("Durum", style="green")

    for sub in sorted(all_subs):
        status = "[green]● Canlı[/green]" if sub in live_subs else "[dim]○ Pasif[/dim]"
        table.add_row(sub, status)

    console.print(table)
    console.print(f"\n[bold]Toplam: {len(all_subs)} alt alan adı[/bold] | "
                 f"[green]Canlı: {len(live_subs)}[/green]\n")
