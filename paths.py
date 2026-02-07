"""Yol keşfi - gobuster veya feroxbuster."""

import tempfile
import urllib.request
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table

from .utils import check_tool, get_tool_missing_message, run_cmd

console = Console()

# İlginç sayılabilecek path'ler (dikkat çekici)
INTERESTING_PATHS = ["admin", "upload", "backup", "config", "api", "login", "dashboard", "wp-admin"]

# Sistem wordlist yoksa kullanılacak minimal liste
MINIMAL_WORDLIST = [
    "admin", "api", "login", "logout", "dashboard", "config", "backup",
    "upload", "uploads", "images", "img", "css", "js", "static", "assets",
    "wp-admin", "wp-login", "phpmyadmin", ".git", "robots.txt", "sitemap.xml",
]


def _create_minimal_wordlist() -> Optional[str]:
    """Geçici minimal wordlist dosyası oluştur."""
    try:
        fd, path = tempfile.mkstemp(suffix=".txt", prefix="sahin_wordlist_")
        with open(fd, "w") as f:
            f.write("\n".join(MINIMAL_WORDLIST))
        return path
    except OSError:
        return None


def run_gobuster(
    url: str,
    wordlist: str,
    timeout: int = 300,
) -> list[tuple[str, int, int]]:
    """
    gobuster dir ile path keşfi.
    Returns: [(path, status_code, size)]
    """
    results = []
    tool_path = check_tool("gobuster")
    if not tool_path:
        return results

    if not Path(wordlist).exists():
        return results

    # -k: SSL doğrulamasını atla (self-signed cert'ler için)
    # -q: sessiz, -t: thread sayısı, -z: progress bar yok (temiz çıktı)
    cmd = [tool_path, "dir", "-u", url, "-w", wordlist, "-q", "-z", "-t", "20", "-k"]

    code, output = run_cmd(cmd, timeout=timeout)
    if code != 0:
        return results

    # Gobuster: /path (Status: 200) [Size: 1234] veya /path (Status: 301) [Size: 318] [--> url]
    for line in output.split("\n"):
        line = line.strip()
        if not line or "(Status:" not in line:
            continue
        try:
            parts = line.split()
            path_part = parts[0]
            status_str = line.split("Status:")[1].split(")")[0].strip()
            status = int(status_str)
            size = 0
            if "Size:" in line:
                try:
                    size_str = line.split("Size:")[1].split("]")[0].strip()
                    size = int(size_str)
                except (ValueError, IndexError):
                    pass
            if path_part.startswith("/"):
                results.append((path_part, status, size))
        except (ValueError, IndexError):
            pass
    return results


def run_feroxbuster(
    url: str,
    wordlist: str,
    timeout: int = 300,
) -> list[tuple[str, int, int]]:
    """
    feroxbuster ile path keşfi.
    Returns: [(path, status_code, size)]
    """
    results = []
    tool_path = check_tool("feroxbuster")
    if not tool_path:
        return results

    if not Path(wordlist).exists():
        return results

    # -k: SSL doğrulamasını atla
    cmd = [
        tool_path, "-u", url,
        "-w", wordlist,
        "-q", "--silent", "-k",
    ]

    code, output = run_cmd(cmd, timeout=timeout)
    if code != 0:
        return results

    # --silent: sadece URL'ler (https://host/path)
    # Normal: STATUS  METHOD  SIZE  URL
    for line in output.split("\n"):
        line = line.strip()
        if not line:
            continue
        # URL formatı: https://example.com/path
        if line.startswith("http"):
            parsed = urlparse(line)
            path_part = parsed.path or "/"
            results.append((path_part, 200, 0))  # Silent'te status yok
            continue
        # Tab-separated: 200  GET  1234  /path
        parts = line.split()
        if len(parts) >= 2:
            for i, p in enumerate(parts):
                if p.startswith("/"):
                    status = int(parts[i - 1]) if i > 0 and parts[i - 1].isdigit() else 200
                    results.append((p, status, 0))
                    break
    return results


def discover_paths(
    base_url: str,
    wordlist: Optional[str] = None,
    use_ferox: bool = True,
    quiet: bool = False,
) -> list[tuple[str, int, int]]:
    """
    Yol keşfi - feroxbuster tercih, yoksa gobuster.
    Kelime listesi: -w ile verilir, yoksa proje/common.txt, sistem wordlist'leri aranır.
    """
    default_paths = [
        # Önce proje klasöründeki wordlist'ler
        str(Path.cwd() / "common.txt"),
        str(Path(__file__).resolve().parent.parent / "common.txt"),
        # Sistem wordlist'leri
        "/usr/share/wordlists/dirb/common.txt",
        "/usr/share/wordlists/dirbuster/directory-list-2.3-small.txt",
        "/usr/share/seclists/Discovery/Web-Content/common.txt",
    ]

    wl = wordlist
    if not wl or not Path(wl).exists():
        for p in default_paths:
            if Path(p).exists():
                wl = p
                break
        else:
            # Minimal built-in wordlist
            wl = _create_minimal_wordlist()
            if not wl:
                if not quiet:
                    console.print("[yellow]⚠ Kelime listesi bulunamadı. Yol keşfi atlanıyor.[/yellow]")
                return []

    results = []
    tool_name = "feroxbuster" if (use_ferox and check_tool("feroxbuster")) else ("gobuster" if check_tool("gobuster") else None)

    if tool_name:
        if not quiet:
            progress = Progress(
                SpinnerColumn(style="bold magenta"),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(bar_width=40, style="magenta"),
                console=console,
            )
            task = progress.add_task(f"[{tool_name}] Yollar taranıyor...", total=None)
            progress.start()
        if tool_name == "feroxbuster":
            results = run_feroxbuster(base_url, wl, timeout=180)
        else:
            results = run_gobuster(base_url, wl, timeout=180)
        if not quiet:
            progress.stop()
    else:
        if not quiet:
            console.print(f"[yellow]⚠ gobuster/feroxbuster {get_tool_missing_message()}[/yellow]")
            console.print("[dim]  → bash requirements/install-tools.sh[/dim]")
        return []

    return results


def is_interesting(path: str) -> bool:
    """Path ilginç mi? (admin, upload vb.)"""
    path_lower = path.lower().strip("/")
    return any(p in path_lower for p in INTERESTING_PATHS)


def _fetch_url(url: str, timeout: int = 5, verify_ssl: bool = False) -> Optional[str]:
    """URL'den içerik çek. Hata olursa None."""
    import ssl
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Sahin/1.0"})
        ctx = ssl.create_default_context()
        if not verify_ssl:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception:
        return None


def _get_robots_and_sitemap(base_url: str) -> tuple[list[str], list[str]]:
    """robots.txt ve sitemap.xml'den path'leri çıkar."""
    robots_paths = []
    sitemap_paths = []
    base = base_url.rstrip("/")

    # robots.txt
    robots_content = _fetch_url(f"{base}/robots.txt")
    if robots_content:
        for line in robots_content.split("\n"):
            line = line.strip().lower()
            if line.startswith("disallow:") and len(line) > 9:
                p = line[9:].strip()
                if p and p != "/":
                    robots_paths.append(p)
            elif line.startswith("sitemap:"):
                sitemap_url = line[8:].strip()
                if sitemap_url:
                    sm = _fetch_url(sitemap_url)
                    if sm and "<loc>" in sm:
                        for part in sm.split("<loc>")[1:]:
                            loc = part.split("</loc>")[0].strip()
                            if loc and not loc.startswith("http"):
                                continue
                            parsed = urlparse(loc)
                            if parsed.path and parsed.path != "/":
                                sitemap_paths.append(parsed.path)

    # sitemap.xml (direkt)
    sitemap_content = _fetch_url(f"{base}/sitemap.xml")
    if sitemap_content and "<loc>" in sitemap_content:
        for part in sitemap_content.split("<loc>")[1:]:
            loc = part.split("</loc>")[0].strip()
            parsed = urlparse(loc)
            if parsed.path and parsed.path != "/":
                sitemap_paths.append(parsed.path)

    return list(dict.fromkeys(robots_paths))[:15], list(dict.fromkeys(sitemap_paths))[:15]


def print_path_results(
    results: list[tuple[str, int, int]],
    base_url: str,
    quiet: bool = False,
):
    """Path keşfi sonuçlarını formatla."""
    if quiet:
        return

    if not results:
        console.print("[dim]Yol bulunamadı.[/dim]")
        console.print("[dim]  • Site statik olabilir veya farklı yapıda[/dim]")
        console.print("[dim]  • robots.txt / sitemap.xml kullanılıyor olabilir[/dim]")
        robots_paths, sitemap_paths = _get_robots_and_sitemap(base_url)
        if robots_paths or sitemap_paths:
            console.print("\n[bold]Dikkat edilmesi gerekenler (robots/sitemap):[/bold]")
            for p in robots_paths[:8]:
                console.print(f"  [yellow]→[/yellow] {p}")
            for p in sitemap_paths[:8]:
                if p not in robots_paths:
                    console.print(f"  [cyan]→[/cyan] {p}")
        return

    table = Table(title=f"Yol Keşfi - {base_url}", show_header=True)
    table.add_column("Yol", style="cyan")
    table.add_column("Durum", style="yellow")
    table.add_column("Not", style="green")

    for path, status, size in results:
        note = ""
        if is_interesting(path):
            note = "[bold red]<!> dikkat[/bold red]"
        elif status == 200:
            note = "[green]erişilebilir[/green]"
        elif status == 403:
            note = "[yellow]yasaklı[/yellow]"

        table.add_row(path, str(status), note)

    console.print(table)
