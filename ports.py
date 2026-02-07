"""Port taraması - nmap."""

from typing import Optional

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table

from .utils import check_tool, get_tool_missing_message, run_cmd

console = Console()

# Yaygın portlar ve servisleri
COMMON_PORTS = {
    21: "FTP",
    22: "SSH",
    23: "Telnet",
    25: "SMTP",
    53: "DNS",
    80: "HTTP",
    110: "POP3",
    143: "IMAP",
    443: "HTTPS",
    445: "SMB",
    3306: "MySQL",
    3389: "RDP",
    5432: "PostgreSQL",
    8080: "HTTP-Alt",
    8443: "HTTPS-Alt",
}

# Port bazlı yorumlar (kullanıcıya ipucu)
PORT_NOTES = {
    8080: "genelde admin panel / alternatif servis",
    8443: "genelde admin panel / alternatif servis",
    3389: "uzak masaüstü — dikkat",
    3306: "veritabanı — dışarı açıksa risk",
}


def run_nmap(host: str, ports: Optional[str] = None, fast: bool = False) -> dict[int, str]:
    """
    nmap ile port taraması + servis bilgisi (-sV).
    Returns: {port: "servis" veya "servis versiyon"}
    """
    results = {}
    path = check_tool("nmap")
    if not path:
        return results

    port_arg = ports or ("-F" if fast else "-p 21,22,23,25,53,80,110,143,443,445,3306,3389,5432,8080,8443")
    # -sT: root gerektirmez, -sV: servis/versiyon tespiti
    cmd = ["nmap", "-Pn", "-sT", "-sV", "--open", port_arg, "-oG", "-", host]
    if fast:
        cmd.remove("-sV")  # Hızlı modda servis tespiti atla

    code, output = run_cmd(cmd, timeout=300)
    if code != 0:
        return results

    # Parse: port/state/protocol//service//version/
    for line in output.split("\n"):
        if "Ports:" in line:
            for p in line.split("Ports:")[1].strip().split(","):
                p = p.strip()
                if "/" in p:
                    segs = p.split("/")
                    try:
                        port = int(segs[0])
                        if len(segs) > 1 and "open" in segs[1].lower():
                            service = COMMON_PORTS.get(port, "?")
                            if len(segs) >= 5 and segs[4]:
                                service = segs[4]
                                if len(segs) >= 6 and segs[5]:
                                    service = f"{segs[4]} {segs[5]}"
                            results[port] = service.strip()
                    except (ValueError, IndexError):
                        pass
    return results


def scan_ports(
    hosts: list[str],
    fast: bool = False,
    quiet: bool = False,
) -> dict[str, dict[int, str]]:
    """
    Birden fazla host için port taraması.
    Returns: {host: {port: service}}
    """
    if not check_tool("nmap"):
        if not quiet:
            console.print(f"[yellow]⚠ nmap {get_tool_missing_message()}[/yellow]")
            console.print("[dim]  → bash requirements/install-tools.sh[/dim]")
        return {}

    all_results = {}
    total = len(hosts)
    if total == 0:
        return all_results

    if not quiet:
        progress = Progress(
            SpinnerColumn(style="bold cyan"),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=40, style="cyan"),
            TaskProgressColumn(),
            console=console,
        )
        task = progress.add_task("Portlar taranıyor...", total=total)
        progress.start()

    for i, host in enumerate(hosts):
        if not quiet:
            progress.update(task, description=f"[{host}] taranıyor...", completed=i)
        results = run_nmap(host, fast=fast)
        if results:
            all_results[host] = results
        if not quiet:
            progress.update(task, completed=i + 1)

    if not quiet:
        progress.stop()

    return all_results


def print_port_results(
    results: dict[str, dict[int, str]],
    quiet: bool = False,
    verbose: bool = False,
):
    """Port tarama sonuçlarını Türkçe formatla yazdır."""
    if quiet:
        return

    for host, ports in results.items():
        console.print(f"\n[bold cyan]{host}[/bold cyan]")
        for port, service in sorted(ports.items()):
            note = PORT_NOTES.get(port, "")
            extra = f" [dim]— {note}[/dim]" if note else ""
            console.print(f"  [green][+][/green] {port} açık ({service}){extra}")
        if not ports:
            console.print("  [dim]Açık port bulunamadı.[/dim]")
        else:
            # SSL özeti
            has_443 = 443 in ports
            has_80 = 80 in ports
            if has_443:
                console.print("  [dim]🔒 SSL: Var (443)[/dim]")
            elif has_80:
                console.print("  [dim]🔓 SSL: Yok (sadece HTTP)[/dim]")
        if verbose:
            console.print("  [dim](nmap -Pn -sT kullanıldı)[/dim]")
