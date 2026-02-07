#!/bin/bash
# ŞAHİN - Gerekli araçların otomatik kurulumu
# Kullanım: ./requirements/install-tools.sh
# veya: bash requirements/install-tools.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_ok() { echo -e "${GREEN}[✓]${NC} $1"; }
log_info() { echo -e "${YELLOW}[*]${NC} $1"; }
log_skip() { echo -e "${YELLOW}[~]${NC} $1 (zaten kurulu veya atlandı)"; }
log_err() { echo -e "${RED}[!]${NC} $1"; }

# OS tespiti
detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    elif [[ -f /etc/debian_version ]]; then
        echo "debian"
    elif [[ -f /etc/redhat-release ]] || [[ -f /etc/fedora-release ]]; then
        echo "rhel"
    else
        echo "unknown"
    fi
}

# Paket yöneticisi ile kur
install_nmap() {
    if command -v nmap &>/dev/null; then
        log_skip "nmap zaten kurulu: $(nmap --version 2>/dev/null | head -1)"
        return 0
    fi
    log_info "nmap kuruluyor..."
    case $(detect_os) in
        macos)   brew install nmap ;;
        debian) sudo apt-get update && sudo apt-get install -y nmap ;;
        rhel)   sudo dnf install -y nmap || sudo yum install -y nmap ;;
        *)      log_err "nmap için paket yöneticisi bulunamadı. Manuel kur: https://nmap.org/download.html" ;;
    esac
    log_ok "nmap kuruldu"
}

# Go araçları
install_go_tools() {
    if ! command -v go &>/dev/null; then
        log_skip "Go yok - subfinder atlanıyor"
        log_info "Go kurmak için: https://go.dev/dl/"
        return 1
    fi

    GOPATH=${GOPATH:-$HOME/go}
    export PATH=$PATH:$GOPATH/bin

    # subfinder
    if command -v subfinder &>/dev/null; then
        log_skip "subfinder zaten kurulu"
    else
        log_info "subfinder kuruluyor..."
        go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest 2>/dev/null || log_err "subfinder kurulamadı"
    fi

    log_info "Go bin: $GOPATH/bin - PATH'e ekleyin: export PATH=\$PATH:\$GOPATH/bin"
    log_info "ŞAHİN otomatik olarak ~/go/bin'i de kontrol eder."
}

# Path keşfi araçları
install_path_tools() {
    # gobuster - paket yöneticisi veya go
    if command -v gobuster &>/dev/null; then
        log_skip "gobuster zaten kurulu"
        return 0
    fi

    case $(detect_os) in
        debian)
            log_info "gobuster kuruluyor..."
            sudo apt-get update && sudo apt-get install -y gobuster 2>/dev/null && log_ok "gobuster kuruldu" || true
            ;;
        macos)
            if command -v brew &>/dev/null; then
                log_info "gobuster kuruluyor..."
                brew install gobuster 2>/dev/null && log_ok "gobuster kuruldu" || true
            fi
            ;;
    esac

    # feroxbuster - Rust (gobuster alternatifi)
    if command -v feroxbuster &>/dev/null; then
        log_skip "feroxbuster zaten kurulu"
        return 0
    fi

    if command -v cargo &>/dev/null; then
        log_info "feroxbuster kuruluyor..."
        cargo install feroxbuster 2>/dev/null && log_ok "feroxbuster kuruldu" || log_err "feroxbuster kurulamadı"
    else
        log_skip "cargo/Rust yok - feroxbuster atlandı"
        log_info "Rust kurmak için: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
    fi
}

# Ana kurulum
main() {
    echo ""
    echo "╔═══════════════════════════════════════╗"
    echo "║   ŞAHİN - Araç Kurulumu              ║"
    echo "╚═══════════════════════════════════════╝"
    echo ""

    log_info "OS: $(detect_os)"
    echo ""

    install_nmap
    echo ""
    install_go_tools
    echo ""
    install_path_tools

    echo ""
    echo "═══════════════════════════════════════"
    log_ok "Kurulum tamamlandı!"
    echo ""
    echo "PATH'e Go bin ekleyin (gerekirse):"
    echo "  export PATH=\$PATH:\$HOME/go/bin"
    echo ""
    echo "Kontrol: sahin -d example.com --help"
    echo ""
}

main "$@"
