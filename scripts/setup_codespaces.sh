#!/usr/bin/env bash
set -euo pipefail

echo "==> Atualizando dependencias Python"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if command -v google-chrome >/dev/null 2>&1; then
  echo "==> Google Chrome ja instalado: $(google-chrome --version)"
  exit 0
fi

echo "==> Instalando Google Chrome no Codespaces"
wget -q -O /tmp/google-chrome-stable_current_amd64.deb \
  https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb

sudo apt-get update
sudo apt-get install -y /tmp/google-chrome-stable_current_amd64.deb

echo "==> Google Chrome instalado: $(google-chrome --version)"
echo "==> Caminho: $(which google-chrome)"
