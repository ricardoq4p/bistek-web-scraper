# Docker

Este projeto pode usar MySQL em Docker para salvar os produtos raspados.

## Subir o banco

```powershell
docker compose up -d
```

Servicos:

- MySQL: `127.0.0.1:3306`
- Adminer: `http://localhost:8080`

Credenciais MySQL:

- servidor: `mysql` no Adminer, ou `127.0.0.1` no Python local
- usuario: `root`
- senha: `admin`
- banco: `bistek`

## Rodar o scraper

```powershell
pip install -r requirements.txt
python main.py
```

O scraper le estas variaveis de ambiente:

```powershell
$env:MYSQL_HOST="127.0.0.1"
$env:MYSQL_PORT="3306"
$env:MYSQL_USER="root"
$env:MYSQL_PASSWORD="admin"
```

## Parar

```powershell
docker compose down
```

Para apagar os dados do banco:

```powershell
docker compose down -v
```
