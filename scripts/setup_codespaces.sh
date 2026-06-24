#!/usr/bin/env bash
set -euo pipefail

echo "==> Atualizando dependencias Python"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if command -v google-chrome >/dev/null 2>&1; then
  echo "==> Google Chrome ja instalado: $(google-chrome --version)"
  exit 0
fi

wait_for_apt() {
  echo "==> Aguardando apt/dpkg liberar locks"
  while sudo fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 \
    || sudo fuser /var/lib/dpkg/lock >/dev/null 2>&1 \
    || sudo fuser /var/cache/apt/archives/lock >/dev/null 2>&1; do
    echo "    apt/dpkg ainda esta ocupado. Tentando novamente em 5s..."
    sleep 5
  done
}

echo "==> Instalando Google Chrome no Codespaces"
wait_for_apt
sudo apt-get update
sudo apt-get install -y wget ca-certificates

wget -q -O /tmp/google-chrome-stable_current_amd64.deb \
  https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb

wait_for_apt
sudo apt-get install -y /tmp/google-chrome-stable_current_amd64.deb

echo "==> Google Chrome instalado: $(google-chrome --version)"
echo "==> Caminho: $(which google-chrome)"
