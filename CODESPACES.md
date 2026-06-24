# GitHub Codespaces

Este projeto nao precisa versionar o arquivo `google-chrome-stable_current_amd64.deb`.

O Codespaces instala o Google Chrome automaticamente pelo script:

```bash
bash scripts/setup_codespaces.sh
```

O script:

- instala as dependencias Python de `requirements.txt`
- instala `pip` se o ambiente vier sem ele
- no Debian/Ubuntu, baixa e instala o Google Chrome oficial
- no Alpine, instala Chromium e Chromedriver pelos pacotes `apk`
- confirma o navegador instalado e o caminho do binario

Depois de criar ou reconstruir o Codespace, rode:

```bash
python main.py
```

Se o Codespace abrir em modo de recuperacao ou aparecer uma imagem Alpine, rode **Codespaces: Rebuild Container** pelo Command Palette depois de atualizar o repositorio. O projeto usa a imagem `mcr.microsoft.com/devcontainers/universal:2`, que ja traz um ambiente mais completo para Python e Docker.

Se o script avisar que `apt/dpkg` esta ocupado, aguarde. Ele tenta novamente automaticamente ate o lock ser liberado.

Se o ambiente vier sem `pip`, o script instala `python3-pip` automaticamente antes de instalar as dependencias do projeto.

Se o Codespace estiver usando Alpine, o navegador sera `chromium` ou `chromium-browser`, e o scraper detecta esse binario automaticamente.

Para abrir a pagina de consulta:

```bash
python app.py
```

Acesse a porta `5000` na aba **Ports** do Codespaces.
