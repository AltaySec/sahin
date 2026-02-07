"""Yardımcı fonksiyonlar ve tool kontrolü."""

import shutil
import subprocess
from typing import Optional


def check_tool(tool_name: str) -> Optional[str]:
    """
    Sistemde tool var mı kontrol et.
    Varsa path döner, yoksa None.
    Go araçları için GOPATH/bin ve ~/go/bin de kontrol edilir.
    """
    path = shutil.which(tool_name)
    if path:
        return path
    # Go ile kurulan araçlar genelde ~/go/bin'de, PATH'te olmayabilir
    import os
    for base in [
        os.environ.get("GOPATH", ""),
        os.path.expanduser("~/go"),
    ]:
        if base:
            go_bin = os.path.join(base, "bin", tool_name)
            if os.path.isfile(go_bin) and os.access(go_bin, os.X_OK):
                return go_bin
    return None


def require_tool(tool_name: str, friendly_name: str = None) -> str:
    """
    Tool'u zorunlu kıl. Yoksa hata mesajı ile çık.
    """
    path = check_tool(tool_name)
    if path:
        return path
    name = friendly_name or tool_name
    raise SystemExit(f"\n[!] {name} {get_tool_missing_message()}")


def get_tool_missing_message() -> str:
    """Tool bulunamadığında gösterilecek mesaj."""
    from .banner import MESSAGES
    return MESSAGES["tool_missing"]


def run_cmd(cmd: list[str], timeout: int = 300, capture: bool = True) -> tuple[int, str]:
    """
    Komut çalıştır, (exit_code, output) döner.
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            timeout=timeout,
        )
        output = result.stdout + result.stderr if capture else ""
        return result.returncode, output
    except subprocess.TimeoutExpired:
        return -1, ""
    except FileNotFoundError:
        return -1, ""


def run_cmd_stream(cmd: list[str], timeout: int = 300, on_line=None) -> tuple[int, str]:
    """
    Komut çalıştır, her satır geldikçe on_line(line) çağır.
    (exit_code, full_output) döner.
    """
    import threading
    output_lines = []
    proc = None
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        def read_stream():
            for line in iter(proc.stdout.readline, ""):
                line = line.rstrip()
                if line:
                    output_lines.append(line)
                    if on_line:
                        on_line(line)

        reader = threading.Thread(target=read_stream)
        reader.daemon = True
        reader.start()
        proc.wait(timeout=timeout)
        reader.join(timeout=1)
        return proc.returncode, "\n".join(output_lines)
    except subprocess.TimeoutExpired:
        if proc:
            proc.kill()
        return -1, "\n".join(output_lines)
    except FileNotFoundError:
        return -1, ""
