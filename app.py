import os
from decimal import Decimal

import pymysql
from flask import Flask, jsonify, render_template, request


app = Flask(__name__)


def conectar_mysql():
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", "admin"),
        database=os.getenv("MYSQL_DATABASE", "bistek"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def serializar_valor(valor):
    if isinstance(valor, Decimal):
        return float(valor)
    return valor


def buscar_resumo():
    sql = """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN precoClube IS NOT NULL THEN 1 ELSE 0 END) AS comPrecoClube,
            AVG(preco) AS precoMedio,
            MAX(dataColeta) AS ultimaColeta
        FROM produtos
    """

    with conectar_mysql() as conexao:
        with conexao.cursor() as cursor:
            cursor.execute(sql)
            return cursor.fetchone()


def buscar_produtos(termo="", apenas_clube=False):
    filtros = []
    parametros = []

    if termo:
        filtros.append("nomeProduto LIKE %s")
        parametros.append(f"%{termo}%")

    if apenas_clube:
        filtros.append("precoClube IS NOT NULL")

    where = f"WHERE {' AND '.join(filtros)}" if filtros else ""
    sql = f"""
        SELECT
            id,
            nomeProduto,
            preco,
            precoClube,
            link,
            dataColeta
        FROM produtos
        {where}
        ORDER BY dataColeta DESC, id DESC
        LIMIT 500
    """

    with conectar_mysql() as conexao:
        with conexao.cursor() as cursor:
            cursor.execute(sql, parametros)
            return cursor.fetchall()


@app.template_filter("dinheiro")
def formatar_dinheiro(valor):
    if valor is None:
        return "-"
    return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@app.template_filter("datahora")
def formatar_datahora(valor):
    if not valor:
        return "-"
    return valor.strftime("%d/%m/%Y %H:%M")


@app.route("/")
def index():
    termo = request.args.get("q", "").strip()
    apenas_clube = request.args.get("clube") == "1"

    erro = None
    resumo = {"total": 0, "comPrecoClube": 0, "precoMedio": None, "ultimaColeta": None}
    produtos = []

    try:
        resumo = buscar_resumo()
        produtos = buscar_produtos(termo=termo, apenas_clube=apenas_clube)
    except Exception as exc:
        erro = str(exc)

    return render_template(
        "index.html",
        erro=erro,
        resumo=resumo,
        produtos=produtos,
        termo=termo,
        apenas_clube=apenas_clube,
    )


@app.route("/api/produtos")
def api_produtos():
    termo = request.args.get("q", "").strip()
    apenas_clube = request.args.get("clube") == "1"
    produtos = buscar_produtos(termo=termo, apenas_clube=apenas_clube)
    return jsonify([{chave: serializar_valor(valor) for chave, valor in item.items()} for item in produtos])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)
