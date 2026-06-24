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

install_with_apt() {
  wait_for_apt
  sudo apt-get update
  sudo apt-get install -y "$@"
}

install_with_apk() {
  sudo apk add --no-cache "$@"
}

install_packages() {
  if command -v apt-get >/dev/null 2>&1; then
    install_with_apt "$@"
  elif command -v apk >/dev/null 2>&1; then
    install_with_apk "$@"
  else
    echo "Gerenciador de pacotes nao suportado. Instale manualmente: $*"
    exit 1
  fi
}

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi
VENV_DIR="${VENV_DIR:-.venv}"

echo "==> Garantindo pip no ambiente"
if ! "$PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    install_with_apt python3-pip python3-venv
  elif command -v apk >/dev/null 2>&1; then
    install_with_apk py3-pip py3-virtualenv
  else
    echo "Nao foi possivel instalar pip automaticamente."
    exit 1
  fi
fi

echo "==> Preparando ambiente virtual em $VENV_DIR"
if [ ! -d "$VENV_DIR" ]; then
  if ! "$PYTHON_BIN" -m venv "$VENV_DIR" >/dev/null 2>&1; then
    if command -v apt-get >/dev/null 2>&1; then
      install_with_apt python3-venv
    elif command -v apk >/dev/null 2>&1; then
      install_with_apk py3-virtualenv
    fi

    if ! "$PYTHON_BIN" -m venv "$VENV_DIR" >/dev/null 2>&1; then
      "$PYTHON_BIN" -m virtualenv "$VENV_DIR"
    fi
  fi
fi

# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

echo "==> Atualizando dependencias Python na virtualenv"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo "==> Virtualenv pronta. Ative com: source $VENV_DIR/bin/activate"

if command -v google-chrome >/dev/null 2>&1; then
  echo "==> Google Chrome ja instalado: $(google-chrome --version)"
  echo "==> Caminho: $(which google-chrome)"
elif command -v chromium-browser >/dev/null 2>&1; then
  echo "==> Chromium ja instalado: $(chromium-browser --version)"
  echo "==> Caminho: $(which chromium-browser)"
elif command -v chromium >/dev/null 2>&1; then
  echo "==> Chromium ja instalado: $(chromium --version)"
  echo "==> Caminho: $(which chromium)"
else
  if command -v apt-get >/dev/null 2>&1; then
    echo "==> Instalando Google Chrome no Codespaces Debian/Ubuntu"
    install_with_apt wget ca-certificates

    wget -q -O /tmp/google-chrome-stable_current_amd64.deb \
      https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb

    wait_for_apt
    sudo apt-get install -y /tmp/google-chrome-stable_current_amd64.deb

    echo "==> Google Chrome instalado: $(google-chrome --version)"
    echo "==> Caminho: $(which google-chrome)"
  elif command -v apk >/dev/null 2>&1; then
    echo "==> Instalando Chromium no Codespaces Alpine"
    install_with_apk chromium chromium-chromedriver nss freetype harfbuzz ttf-freefont
    echo "==> Chromium instalado: $(chromium-browser --version 2>/dev/null || chromium --version)"
    echo "==> Caminho Chromium: $(which chromium-browser 2>/dev/null || which chromium)"
    echo "==> Caminho ChromeDriver: $(which chromedriver)"
  else
    echo "Nenhum gerenciador de pacotes suportado encontrado para instalar navegador."
    exit 1
  fi
fi

if command -v docker >/dev/null 2>&1; then
  echo "==> Docker encontrado: $(docker --version)"
else
  if command -v apk >/dev/null 2>&1; then
    echo "==> Instalando Docker CLI no Alpine"
    install_with_apk docker-cli docker-cli-compose
    docker --version || true
  else
    echo "==> Docker nao encontrado. Execute Codespaces: Rebuild Container para aplicar o recurso Docker."
  fi
fi
