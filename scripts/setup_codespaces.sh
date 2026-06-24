#!/usr/bin/env bash
set -euo pipefail

wait_for_apt() {
  echo "==> Aguardando apt/dpkg liberar locks"
  while sudo fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 \
    || sudo fuser /var/lib/dpkg/lock >/dev/null 2>&1 \
    || sudo fuser /var/cache/apt/archives/lock >/dev/null 2>&1; do
    echo "    apt/dpkg ainda esta ocupado. Tentando novamente em 5s..."
    sleep 5
  done
}

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi

echo "==> Garantindo pip no ambiente"
if ! "$PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
  wait_for_apt
  sudo apt-get update
  sudo apt-get install -y python3-pip python3-venv
fi

echo "==> Atualizando dependencias Python"
"$PYTHON_BIN" -m pip install --user --upgrade pip
"$PYTHON_BIN" -m pip install --user -r requirements.txt

if command -v google-chrome >/dev/null 2>&1; then
  echo "==> Google Chrome ja instalado: $(google-chrome --version)"
  echo "==> Caminho: $(which google-chrome)"
else
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
fi

if command -v docker >/dev/null 2>&1; then
  echo "==> Docker encontrado: $(docker --version)"
else
  echo "==> Docker nao encontrado. Execute Codespaces: Rebuild Container para aplicar o recurso Docker."
fi
