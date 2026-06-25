import html
import os
from datetime import datetime
from statistics import mean
from typing import Iterable

from dotenv import load_dotenv
import yagmail


load_dotenv()


def _formatar_moeda(valor):
    if valor is None:
        return "-"
    return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _formatar_data() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def _produto_para_linha(produto):
    nome = html.escape(produto.nome or "-")
    categoria = html.escape(produto.categoria or "-")
    unidade = html.escape(produto.preco_por_unidade or "-")
    desconto = html.escape(produto.desconto or "-")
    link = html.escape(produto.link or "")
    preco_antigo = _formatar_moeda(produto.preco_antigo)
    preco_atual = _formatar_moeda(produto.preco_atual)
    preco_clube = _formatar_moeda(produto.preco_clube)

    link_html = f'<a href="{link}" target="_blank">Abrir</a>' if link else "-"
    return f"""
        <tr>
          <td style="padding:10px;border-bottom:1px solid #edf1f3;">{nome}</td>
          <td style="padding:10px;border-bottom:1px solid #edf1f3;">{categoria}</td>
          <td style="padding:10px;border-bottom:1px solid #edf1f3;">{preco_antigo}</td>
          <td style="padding:10px;border-bottom:1px solid #edf1f3;">{preco_atual}</td>
          <td style="padding:10px;border-bottom:1px solid #edf1f3;">{preco_clube}</td>
          <td style="padding:10px;border-bottom:1px solid #edf1f3;">{unidade}</td>
          <td style="padding:10px;border-bottom:1px solid #edf1f3;">{desconto}</td>
          <td style="padding:10px;border-bottom:1px solid #edf1f3;">{link_html}</td>
        </tr>
    """


def montar_html_email(produtos: Iterable) -> str:
    produtos = list(produtos)
    total = len(produtos)
    com_clube = sum(1 for produto in produtos if produto.preco_clube is not None)
    precos = [float(produto.preco_atual) for produto in produtos if produto.preco_atual is not None]
    preco_medio = mean(precos) if precos else None
    linhas = "\n".join(_produto_para_linha(produto) for produto in produtos)

    return f"""
    <!doctype html>
    <html lang="pt-BR">
      <body style="margin:0;background:#f5f7f8;font-family:Arial,Helvetica,sans-serif;color:#172026;">
        <div style="max-width:960px;margin:0 auto;padding:24px;">
          <div style="background:#126b5c;color:#fff;padding:22px;border-radius:8px 8px 0 0;">
            <h1 style="margin:0;font-size:24px;">Relatorio Bistek</h1>
            <p style="margin:6px 0 0;color:#d9f1ec;">Coleta realizada em {_formatar_data()}</p>
          </div>

          <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;background:#fff;padding:18px;border-left:1px solid #dfe5e8;border-right:1px solid #dfe5e8;">
            <div style="border:1px solid #dfe5e8;border-radius:8px;padding:14px;">
              <div style="color:#66727d;font-size:13px;">Produtos captados</div>
              <strong style="font-size:24px;">{total}</strong>
            </div>
            <div style="border:1px solid #dfe5e8;border-radius:8px;padding:14px;">
              <div style="color:#66727d;font-size:13px;">Com preco Clube</div>
              <strong style="font-size:24px;">{com_clube}</strong>
            </div>
            <div style="border:1px solid #dfe5e8;border-radius:8px;padding:14px;">
              <div style="color:#66727d;font-size:13px;">Preco medio</div>
              <strong style="font-size:24px;">{_formatar_moeda(preco_medio)}</strong>
            </div>
          </div>

          <div style="background:#fff;padding:0 18px 18px;border:1px solid #dfe5e8;border-top:0;border-radius:0 0 8px 8px;">
            <table style="width:100%;border-collapse:collapse;">
              <thead>
                <tr>
                  <th style="text-align:left;padding:12px;border-bottom:1px solid #dfe5e8;color:#66727d;">Produto</th>
                  <th style="text-align:left;padding:12px;border-bottom:1px solid #dfe5e8;color:#66727d;">Categoria</th>
                  <th style="text-align:left;padding:12px;border-bottom:1px solid #dfe5e8;color:#66727d;">Preco antigo</th>
                  <th style="text-align:left;padding:12px;border-bottom:1px solid #dfe5e8;color:#66727d;">Preco atual</th>
                  <th style="text-align:left;padding:12px;border-bottom:1px solid #dfe5e8;color:#66727d;">Preco Clube</th>
                  <th style="text-align:left;padding:12px;border-bottom:1px solid #dfe5e8;color:#66727d;">Unidade</th>
                  <th style="text-align:left;padding:12px;border-bottom:1px solid #dfe5e8;color:#66727d;">Desconto</th>
                  <th style="text-align:left;padding:12px;border-bottom:1px solid #dfe5e8;color:#66727d;">Link</th>
                </tr>
              </thead>
              <tbody>
                {linhas}
              </tbody>
            </table>
          </div>
        </div>
      </body>
    </html>
    """


def enviar_relatorio_email(produtos: Iterable) -> bool:
    if os.getenv("EMAIL_ENABLED", "0").strip() != "1":
        return False

    usuario = os.getenv("EMAIL_USER", "").strip()
    senha = os.getenv("EMAIL_PASSWORD", "").strip()
    destinatarios = [email.strip() for email in os.getenv("EMAIL_TO", "").split(",") if email.strip()]

    if not usuario or not senha or not destinatarios:
        raise ValueError("Configure EMAIL_USER, EMAIL_PASSWORD e EMAIL_TO para enviar o relatorio.")

    assunto = os.getenv("EMAIL_SUBJECT", "Relatorio Bistek - Produtos captados")
    yag = yagmail.SMTP(user=usuario, password=senha)
    yag.send(to=destinatarios, subject=assunto, contents=montar_html_email(produtos))
    return True
