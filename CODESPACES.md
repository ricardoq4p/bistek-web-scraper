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

Para abrir a pagina de consulta:

```bash
python app.py
```

Acesse a porta `5000` na aba **Ports** do Codespaces.
