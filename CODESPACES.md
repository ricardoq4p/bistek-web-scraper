# GitHub Codespaces

Guia de primeira execucao para quem abriu este repositorio no GitHub Codespaces e quer subir todos os ambientes do projeto na ordem certa.

## O que este projeto usa

- `main.py`: faz o web scraping do site do Bistek
- `app.py`: abre a interface web para consultar os produtos salvos
- `docker compose`: sobe o MySQL e o Adminer
- `.venv`: ambiente virtual Python do projeto

## Portas usadas

- `3306`: MySQL
- `8080`: Adminer
- `5000`: interface Flask
- `5001`: porta alternativa para a interface, caso a `5000` ja esteja ocupada

## Credenciais padrao do banco

Essas credenciais ja estao definidas no projeto:

- host para o Python local no Codespaces: `127.0.0.1`
- host para login no Adminer: `mysql`
- usuario: `root`
- senha: `admin`
- base: `bistek`

## Fluxo cronologico recomendado

### 1. Abrir a raiz do projeto

Assim que o Codespaces abrir, confirme que voce esta na pasta correta:

```bash
cd /workspaces/bistek-web-scraper
pwd
ls
```

O `pwd` deve mostrar:

```bash
/workspaces/bistek-web-scraper
```

O `ls` deve listar, entre outros:

- `app.py`
- `main.py`
- `scripts`
- `templates`
- `docker-compose.yml`

Se voce estiver dentro de `templates/` ou outra subpasta, os comandos do projeto vao falhar por caminho incorreto.

### 2. Fazer rebuild do container quando necessario

Se o Codespaces mostrar um aviso de alteracao no dev container, clique em `Rebuild Now`.

Se o Docker nao existir no terminal, faca:

1. abra o Command Palette
2. rode `Codespaces: Rebuild Container`

Use `Full Rebuild` apenas se o `Rebuild` normal terminar e ainda assim o Docker continuar ausente.

### 3. Confirmar se o Docker esta disponivel

Antes de rodar qualquer coisa do banco, confirme:

```bash
docker --version
docker compose version
```

Se esses dois comandos responderem com versao, o ambiente Docker esta pronto.

Se aparecer `docker: command not found`, volte para a etapa de rebuild.

### 4. Preparar a virtualenv Python

O projeto usa `.venv`. O jeito mais seguro e:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m ensurepip --upgrade
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Se tudo estiver certo, o prompt passa a mostrar algo como:

```bash
(.venv)
```

Voce pode confirmar se a dependencia do MySQL entrou:

```bash
python -m pip show pymysql
```

### 5. Subir o MySQL e o Adminer

Com a raiz do projeto aberta e o Docker funcionando:

```bash
docker compose up -d
docker compose ps
```

O esperado e ver os servicos `mysql` e `adminer` ativos.

### 6. Entrar no Adminer

Abra a porta `8080` na aba **Ports** do Codespaces.

No formulario do Adminer, use exatamente:

- `Sistema`: `MySQL`
- `Servidor`: `mysql`
- `Usuario`: `root`
- `Senha`: `admin`
- `Base de dados`: `bistek`

Importante:

- no Adminer, o campo `Servidor` deve ser `mysql`
- nao use `db`
- nao use `127.0.0.1` nesse formulario do Adminer

Se voce usar `db`, o erro tipico sera algo como:

```text
getaddrinfo for db failed
```

### 7. Executar o web scraping

Com a `.venv` ativa e o MySQL no ar:

```bash
python main.py
```

O esperado no terminal:

- inicializacao do Chrome/Chromium
- abertura do site `https://www.bistek.com.br`
- logs de scroll e coleta
- gravacao dos produtos no MySQL
- mensagem final parecida com:

```text
Processo concluido. Produtos salvos/atualizados: X
```

Se quiser conferir no Adminer, abra a base `bistek` e depois a tabela `produtos`.

### 8. Abrir a interface web

Depois do scraping, suba a aplicacao Flask:

```bash
python app.py
```

Se a porta `5000` ja estiver ocupada:

```bash
PORT=5001 python app.py
```

Abra a porta correspondente na aba **Ports** do Codespaces.

### 9. Validar se tudo ficou funcional

Quando o projeto estiver todo no ar:

- o Adminer deve abrir normalmente
- a base `bistek` deve existir
- a tabela `produtos` deve conter os itens raspados
- a interface web nao deve mais mostrar erro de conexao com MySQL
- a lista de produtos deve aparecer na pagina

## Sequencia curta para uso diario

Depois que o ambiente ja foi preparado pelo menos uma vez, normalmente basta:

```bash
cd /workspaces/bistek-web-scraper
source .venv/bin/activate
docker compose up -d
python main.py
PORT=5001 python app.py
```

## Troubleshooting

### `docker: command not found`

O container foi aberto sem o recurso Docker aplicado corretamente.

Faca:

1. `Codespaces: Rebuild Container`
2. teste novamente:

```bash
docker --version
docker compose version
```

### `ModuleNotFoundError: No module named 'pymysql'`

A `.venv` nao esta ativa ou as dependencias nao foram instaladas nela.

Rode:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Se a `.venv` estiver quebrada:

```bash
deactivate 2>/dev/null || true
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
python -m ensurepip --upgrade
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### `externally-managed-environment`

Isso acontece quando a instalacao tenta usar o Python do sistema em vez da `.venv`.

Crie e ative a virtualenv antes de instalar:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### `Nenhum navegador Chrome/Chromium foi encontrado no ambiente`

O Selenium nao encontrou navegador instalado no Codespaces.

Primeiro tente:

```bash
bash scripts/setup_codespaces.sh
```

Se o script falhar no `apt-get update` por causa do repositório do Yarn, aplique este contorno:

```bash
sudo mv /etc/apt/sources.list.d/yarn.list /etc/apt/sources.list.d/yarn.list.disabled 2>/dev/null || true
sudo apt-get update
sudo apt-get install -y wget ca-certificates
wget -q -O /tmp/google-chrome-stable_current_amd64.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt-get install -y /tmp/google-chrome-stable_current_amd64.deb
google-chrome --version
```

Depois:

```bash
source .venv/bin/activate
python main.py
```

### `Port 5000 is in use`

Suba a interface em outra porta:

```bash
PORT=5001 python app.py
```

### A interface abre, mas mostra erro de MySQL

Isso normalmente significa que o banco ainda nao subiu ou a coleta ainda nao gravou nada.

Confira:

```bash
docker compose ps
```

Depois rode novamente:

```bash
source .venv/bin/activate
python main.py
```

## Encerrar os servicos

Para parar os containers:

```bash
docker compose down
```

Para parar e apagar os dados do banco:

```bash
docker compose down -v
```
