#!/usr/bin/env python3
"""
ŞAHİN - Alt Alan Adı Keşif & Saldırı Yardımcısı
Tek komutla hedef keşfi. AltaySec
"""

import argparse
import sys
import time

from rich.console import Console
from rich.panel import Panel

from . import __version__
from .banner import BANNER, BANNER_ALT, MESSAGES
from .paths import discover_paths, is_interesting, print_path_results
from .ports import print_port_results, scan_ports
from .subdomains import discover_subdomains, print_subdomain_results

console = Console()


def parse_args():
    parser = argparse.ArgumentParser(
        prog="sahin",
        description="ŞAHİN | AltaySec",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Örnek:
  sahin -d example.com
  sahin -d example.com --fast
  sahin -d example.com --quiet
  sahin -d example.com --no-ports --no-paths
        """,
    )
    parser.add_argument("-d", "--domain", required=True, help="Hedef domain (örn: example.com)")
    parser.add_argument("-q", "--quiet", action="store_true", help="Sessiz mod - sadece özet")
    parser.add_argument("--fast", action="store_true", help="Hızlı mod - daha az tarama")
    parser.add_argument("--no-subdomains", action="store_true", help="Alt alan adı keşfini atla")
    parser.add_argument("--no-ports", action="store_true", help="Port taramasını atla")
    parser.add_argument("--no-paths", action="store_true", help="Yol keşfini atla")
    parser.add_argument("--no-live-check", action="store_true", help="Canlı host kontrolünü atla")
    parser.add_argument("-w", "--wordlist", help="Yol keşfi için kelime listesi (varsayılan: common.txt)")
    parser.add_argument("--banner-alt", action="store_true", help="Alternatif (küçük) banner")
    parser.add_argument("--verbose", action="store_true", help="Nmap detayları (Pn, timeout vb.)")
    parser.add_argument("-o", "--output", metavar="DOSYA", help="Sonuçları dosyaya kaydet (txt)")
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")
    return parser.parse_args()


def run(args):
    domain = args.domain.strip().lower()
    if not domain:
        console.print("[red]Domain gerekli.[/red]")
        sys.exit(1)

    start_time = time.time()

    # Banner + versiyon
    banner = BANNER_ALT if args.banner_alt else BANNER
    console.print(Panel(banner, style="bold red", border_style="red"))
    console.print(f"[dim]ŞAHİN v{__version__} | AltaySec[/dim]")
    console.print(f"\n[bold yellow]{MESSAGES['start']}[/bold yellow]\n")

    all_subs = set()
    live_subs = set()
    port_results = {}
    path_results = []
    interesting_count = 0

    # 1. Port taraması (ana domain - her domain kendi portlarını gösterir)
    scan_targets = [domain]
    if not args.no_ports:
        console.print("[bold]1️⃣  Port Taraması[/bold]")
        if not args.quiet:
            console.print(f"[dim]{domain} için portlar taranıyor...[/dim]")
        port_results = scan_ports(scan_targets, fast=args.fast, quiet=args.quiet)
        print_port_results(port_results, quiet=args.quiet, verbose=args.verbose)

    # 2. Alt alan adı keşfi
    if not args.no_subdomains:
        console.print("[bold]2️⃣  Alt Alan Adı Keşfi[/bold]")
        all_subs, live_subs = discover_subdomains(
            domain,
            check_live=not args.no_live_check,
            quiet=args.quiet,
            fast=args.fast,
        )
        print_subdomain_results(all_subs, live_subs, quiet=args.quiet)
    else:
        all_subs = {domain}
        live_subs = {domain}

    # Path keşfi için hedefler
    path_targets = list(live_subs) if live_subs else list(all_subs)[:5]

    # 3. Yol keşfi - HTTP/HTTPS açık olanlara
    if not args.no_paths:
        base_urls = []
        for host in path_targets[:3]:  # Max 3 host
            if host in port_results:
                if 443 in port_results[host]:
                    base_urls.append(f"https://{host}")
                if 80 in port_results[host]:
                    base_urls.append(f"http://{host}")
            else:
                base_urls.append(f"https://{host}")
                base_urls.append(f"http://{host}")

        if not base_urls:
            base_urls = [f"https://{domain}", f"http://{domain}"]

        for url in base_urls[:2]:  # İlk 2 URL
            console.print(f"\n[bold]3️⃣  Yol Keşfi[/bold] - {url}")
            paths = discover_paths(url, wordlist=args.wordlist or None, quiet=args.quiet)
            path_results.extend([(p, s, sz) for p, s, sz in paths])
            print_path_results(paths, url, quiet=args.quiet)

    interesting_count = sum(1 for p, _, _ in path_results if is_interesting(p))

    # Risk seviyesi
    risk_ports = {3389, 3306, 5432, 445}
    open_risk_ports = sum(
        1 for ports in port_results.values()
        for p in ports if p in risk_ports
    )
    if interesting_count >= 2 or open_risk_ports >= 2:
        risk_level = "Orta"
        risk_note = "Manuel inceleme önerilir."
    elif interesting_count >= 1 or open_risk_ports >= 1 or path_results:
        risk_level = "Bilgi"
        risk_note = "İnceleme faydalı olabilir."
    else:
        risk_level = "Düşük"
        risk_note = "Belirgin açık görünmüyor."

    elapsed = int(time.time() - start_time)

    # 4. Özet
    summary_text = f"""
[bold]{MESSAGES['summary']}[/bold]

• {len(all_subs)} alt alan adı bulundu
• {len(live_subs)} canlı host
• {sum(len(p) for p in port_results.values())} açık port
• {len(path_results)} yol bulundu
• {interesting_count} ilginç yol

[bold]Risk seviyesi:[/bold] {risk_level}
[dim]{risk_note}[/dim]

[dim]Tarama süresi: {elapsed} saniye[/dim]
[dim]ŞAHİN v{__version__}[/dim]
"""
    console.print("\n" + "═" * 50)
    console.print(Panel(summary_text, title="🦅", border_style="yellow"))
    console.print("═" * 50 + "\n")

    # Çıktı dosyası
    if args.output:
        _save_output(
            args.output,
            domain=domain,
            all_subs=all_subs,
            live_subs=live_subs,
            port_results=port_results,
            path_results=path_results,
            interesting_count=interesting_count,
            risk_level=risk_level,
            risk_note=risk_note,
            elapsed=elapsed,
        )
        console.print(f"[green]Sonuçlar kaydedildi: {args.output}[/green]\n")


def _save_output(
    path: str,
    domain: str,
    all_subs: set,
    live_subs: set,
    port_results: dict,
    path_results: list,
    interesting_count: int,
    risk_level: str,
    risk_note: str,
    elapsed: int,
):
    """Sonuçları düz metin dosyasına yaz."""
    lines = [
        f"ŞAHİN v{__version__} — {domain}",
        "=" * 50,
        "",
        "Alt Alan Adları:",
        *sorted(all_subs),
        "",
        f"Canlı: {len(live_subs)}",
        "",
        "Portlar:",
    ]
    for host, ports in port_results.items():
        lines.append(f"  {host}:")
        for port, svc in sorted(ports.items()):
            lines.append(f"    {port} - {svc}")
    lines.extend([
        "",
        "Yollar:",
        *[f"  {p} ({s})" for p, s, _ in path_results],
        "",
        f"İlginç yol: {interesting_count}",
        f"Risk: {risk_level} — {risk_note}",
        f"Tarama süresi: {elapsed} saniye",
    ])
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    args = parse_args()
    try:
        run(args)
    except KeyboardInterrupt:
        console.print("\n[yellow]Av iptal edildi.[/yellow]")
        sys.exit(130)
    except Exception as e:
        if "--debug" in sys.argv:
            raise
        console.print(f"[red]Hata: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
