# Relatorio por e-mail

O scraper pode enviar automaticamente um relatorio HTML com os produtos captados.

## Variaveis de ambiente

Configure no Codespaces, no terminal, ou em um arquivo `.env` local:

```bash
EMAIL_ENABLED=1
EMAIL_USER=seu-email@gmail.com
EMAIL_PASSWORD=sua-senha-de-app
EMAIL_TO=destinatario@exemplo.com
EMAIL_SUBJECT="Relatorio Bistek - Produtos captados"
```

Para Gmail, use uma **senha de app**, nao a senha normal da conta.

## Execucao

Depois de configurar as variaveis, rode:

```bash
python main.py
```

O fluxo fica assim:

1. Abre o site do Bistek.
2. Raspa os produtos.
3. Salva no MySQL.
4. Monta um relatorio HTML.
5. Envia o e-mail com os produtos captados.

Se `EMAIL_ENABLED` estiver diferente de `1`, o scraper apenas registra no log que o envio esta desativado.
