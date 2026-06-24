# GitHub Codespaces

Este projeto nao precisa versionar o arquivo `google-chrome-stable_current_amd64.deb`.

O Codespaces instala o Google Chrome automaticamente pelo script:

```bash
bash scripts/setup_codespaces.sh
```

O script:

- instala as dependencias Python de `requirements.txt`
- baixa o instalador oficial do Google Chrome
- instala o Chrome no Linux
- confirma `google-chrome --version`
- confirma `which google-chrome`

Depois de criar ou reconstruir o Codespace, rode:

```bash
python main.py
```

Se o comando `docker` nao existir no terminal, rode **Codespaces: Rebuild Container** pelo Command Palette. O projeto usa o recurso `docker-outside-of-docker` configurado em `.devcontainer/devcontainer.json`.

Se o script avisar que `apt/dpkg` esta ocupado, aguarde. Ele tenta novamente automaticamente ate o lock ser liberado.

Se o ambiente vier sem `pip`, o script instala `python3-pip` automaticamente antes de instalar as dependencias do projeto.

Para abrir a pagina de consulta:

```bash
python app.py
```

Acesse a porta `5000` na aba **Ports** do Codespaces.
