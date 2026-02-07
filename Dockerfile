# ŞAHİN - Tek komutla hedef keşfi | AltaySec

FROM python:3.11-slim

# Sistem bağımlılıkları (nmap vb.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    nmap \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python bağımlılıkları
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ŞAHİN kodu
COPY sahin/ sahin/
COPY pyproject.toml .

RUN pip install --no-cache-dir .

# subfinder, gobuster/feroxbuster
# kullanıcı kendi image'ını build edebilir veya volume mount ile kullanabilir
# Bu base image sadece Python + nmap içerir

ENTRYPOINT ["sahin"]
CMD ["-h"]
