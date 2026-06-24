import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import pymysql
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


BASE_URL = "https://www.bistek.com.br"
DB_NAME = "bistek"
TABLE_NAME = "produtos"
SELETOR_NOME_PRODUTO = ".vtex-flex-layout-0-x-flexRow--container__name"
SELETOR_PRECO_ATUAL = ".vtex-flex-layout-0-x-flexRowContent--container__selling-price"
ARQUIVO_DIAGNOSTICO_HTML = Path("pagina.html")
ARQUIVO_DIAGNOSTICO_SCREENSHOT = Path("pagina.png")


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Produto:
    nome: str
    preco_atual: Optional[float]
    preco_clube: Optional[float]
    preco_por_unidade: str
    desconto: str
    imagem: str
    link: str


@dataclass
class DiagnosticoPagina:
    articles: int = 0
    links_produto: int = 0
    spans_com_preco: int = 0
    elementos_clube: int = 0
    cards_candidatos: int = 0


def limpar_preco(texto: str) -> Optional[float]:
    if not texto:
        return None

    texto = texto.replace("R$", "")
    texto = re.sub(r"\s+", "", texto)
    texto = texto.replace(".", "")
    texto = texto.replace(",", ".")

    if not texto:
        return None

    return float(texto)


def extrair_primeiro_preco(texto: str) -> Optional[float]:
    match = re.search(r"R\$\s*\d[\d\s.]*,\s*\d{2}", texto or "")
    if not match:
        return None

    return limpar_preco(match.group(0))


def limpar_texto(texto: str) -> str:
    return re.sub(r"\s+", " ", texto or "").strip()


def configurar_driver() -> webdriver.Chrome:
    chrome_options = Options()
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--start-maximized")

    headless = os.getenv("HEADLESS", "0").strip() == "1"
    if headless:
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--window-size=1366,1800")

    logger.info("Iniciando Chrome via Selenium.")
    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options,
    )


def aceitar_cookies_se_existir(driver: webdriver.Chrome) -> None:
    textos_botoes = ("aceitar", "aceito", "concordo", "permitir")

    try:
        botoes = driver.find_elements(By.TAG_NAME, "button")
        for botao in botoes:
            texto = limpar_texto(botao.text).lower()
            if any(opcao in texto for opcao in textos_botoes):
                botao.click()
                logger.info("Banner de cookies fechado.")
                time.sleep(1)
                return
    except WebDriverException as erro:
        logger.warning("Nao foi possivel interagir com o banner de cookies: %s", erro)


def pagina_tem_sinal_de_produto(driver: webdriver.Chrome) -> bool:
    return bool(
        driver.execute_script(
            """
            const texto = document.body ? document.body.innerText : '';
            return document.querySelector('a[href*="/p"]')
                || texto.includes('R$')
                || /no\\s+Clube/i.test(texto);
            """
        )
    )


def aguardar_produtos_ou_sinais(driver: webdriver.Chrome, timeout: int = 60) -> None:
    logger.info("Aguardando ate %s segundos por sinais de produto no HTML.", timeout)

    try:
        WebDriverWait(driver, timeout).until(lambda navegador: pagina_tem_sinal_de_produto(navegador))
        logger.info("Sinal de produto encontrado na pagina.")
    except TimeoutException:
        logger.warning("Nenhum link /p, texto R$ ou texto no Clube apareceu em %s segundos.", timeout)


def contar_sinais_selenium(driver: webdriver.Chrome) -> dict[str, int]:
    return driver.execute_script(
        """
        const todos = Array.from(document.querySelectorAll('*'));
        return {
            nomesAntigos: document.querySelectorAll(arguments[0]).length,
            articles: document.querySelectorAll('article').length,
            linksProduto: document.querySelectorAll('a[href*="/p"]').length,
            spansComPreco: Array.from(document.querySelectorAll('span')).filter(
                el => (el.innerText || '').includes('R$')
            ).length,
            elementosClube: todos.filter(el => /no\\s+Clube/i.test(el.innerText || '')).length
        };
        """,
        SELETOR_NOME_PRODUTO,
    )


def rolar_ate_carregar_tudo(driver: webdriver.Chrome, pausa: float = 2.0, limite_sem_mudanca: int = 5) -> None:
    logger.info("Rolando a pagina para carregar todos os produtos.")

    altura_anterior = 0
    qtd_sinais_anterior = 0
    tentativas_sem_mudanca = 0

    while tentativas_sem_mudanca < limite_sem_mudanca:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pausa)

        altura_atual = driver.execute_script("return document.body.scrollHeight")
        sinais = contar_sinais_selenium(driver)
        qtd_sinais_atual = sinais["nomesAntigos"] + sinais["linksProduto"] + sinais["spansComPreco"]

        logger.info(
            "Scroll realizado | altura=%s | nomes antigos=%s | links /p=%s | spans com preco=%s | no Clube=%s",
            altura_atual,
            sinais["nomesAntigos"],
            sinais["linksProduto"],
            sinais["spansComPreco"],
            sinais["elementosClube"],
        )

        if altura_atual == altura_anterior and qtd_sinais_atual == qtd_sinais_anterior:
            tentativas_sem_mudanca += 1
        else:
            tentativas_sem_mudanca = 0

        altura_anterior = altura_atual
        qtd_sinais_anterior = qtd_sinais_atual

    logger.info("Scroll concluido. Nenhum novo produto apareceu nas ultimas tentativas.")


def texto_visivel_do_card(card) -> list[str]:
    return [limpar_texto(texto) for texto in card.stripped_strings if limpar_texto(texto)]


def texto_do_elemento(elemento) -> str:
    return limpar_texto(elemento.get_text(" ", strip=True))


def extrair_nome(nome_tag) -> str:
    return limpar_texto(nome_tag.get("title") or nome_tag.get_text(" ", strip=True))


def nome_parece_produto(nome: str) -> bool:
    if not nome or len(nome) < 4:
        return False

    termos_institucionais = (
        "politica",
        "politicas",
        "política",
        "políticas",
        "privacidade",
        "termos",
        "faq",
        "atendimento",
        "institucional",
        "newsletter",
        "cookies",
    )
    nome_lower = nome.lower()
    return not any(termo in nome_lower for termo in termos_institucionais)


def extrair_nome_do_card(card) -> str:
    nome_tag = card.select_one(SELETOR_NOME_PRODUTO)
    if nome_tag:
        nome = extrair_nome(nome_tag)
        if nome and nome_parece_produto(nome):
            return nome

    for seletor in ("h3 span", "h3", "a[href*='/p'] span", "a[href*='/p']"):
        tag = card.select_one(seletor)
        if not tag:
            continue

        nome = limpar_texto(tag.get("title") or tag.get_text(" ", strip=True))
        if (
            nome
            and nome_parece_produto(nome)
            and "R$" not in nome
            and not re.search(r"no\s+Clube", nome, re.IGNORECASE)
        ):
            return nome

    textos = texto_visivel_do_card(card)
    for texto in textos:
        texto_lower = texto.lower()
        if (
            "r$" not in texto_lower
            and "clube" not in texto_lower
            and "%" not in texto_lower
            and "comprar" not in texto_lower
            and "adicionar" not in texto_lower
            and len(texto) > 3
            and nome_parece_produto(texto)
        ):
            return texto

    return ""


def localizar_bloco_produto(nome_tag):
    bloco_sem_preco = None

    for ancestral in nome_tag.parents:
        if getattr(ancestral, "name", None) not in ("a", "section"):
            continue

        if bloco_sem_preco is None:
            bloco_sem_preco = ancestral

        texto_ancestral = ancestral.get_text(" ", strip=True)
        if "R$" in texto_ancestral:
            return ancestral

    return bloco_sem_preco


def encontrar_cards_candidatos(soup: BeautifulSoup) -> list:
    candidatos = []
    vistos = set()
    tags_card = {"a", "article", "section", "div", "li"}

    for link_tag in soup.select('a[href*="/p"]'):
        for elemento in [link_tag, *list(link_tag.parents)]:
            if getattr(elemento, "name", None) not in tags_card:
                continue
            if elemento.name in ("html", "body"):
                break

            texto = texto_do_elemento(elemento)
            link = extrair_link(elemento)
            nome = extrair_nome_do_card(elemento)

            if "R$" in texto and "/p" in link and nome:
                chave = id(elemento)
                if chave not in vistos:
                    vistos.add(chave)
                    candidatos.append(elemento)
                break

    if not candidatos:
        for elemento in soup.find_all(["article", "section", "div", "li"]):
            texto = texto_do_elemento(elemento)
            link = extrair_link(elemento)
            nome = extrair_nome_do_card(elemento)
            if "R$" in texto and "/p" in link and nome:
                chave = id(elemento)
                if chave not in vistos:
                    vistos.add(chave)
                    candidatos.append(elemento)

    candidatos.sort(key=lambda tag: len(texto_do_elemento(tag)))
    return candidatos


def gerar_diagnostico(soup: BeautifulSoup, cards_candidatos: list) -> DiagnosticoPagina:
    elementos_clube = {
        id(texto.parent)
        for texto in soup.find_all(string=re.compile(r"no\s+Clube", re.IGNORECASE))
        if texto.parent
    }

    return DiagnosticoPagina(
        articles=len(soup.find_all("article")),
        links_produto=len(soup.select('a[href*="/p"]')),
        spans_com_preco=sum(1 for span in soup.find_all("span") if "R$" in texto_do_elemento(span)),
        elementos_clube=len(elementos_clube),
        cards_candidatos=len(cards_candidatos),
    )


def salvar_diagnostico(driver: webdriver.Chrome, soup: BeautifulSoup, diagnostico: DiagnosticoPagina) -> None:
    html = driver.page_source
    ARQUIVO_DIAGNOSTICO_HTML.write_text(html, encoding="utf-8")

    try:
        driver.save_screenshot(str(ARQUIVO_DIAGNOSTICO_SCREENSHOT))
    except WebDriverException as erro:
        logger.warning("Nao foi possivel salvar screenshot de diagnostico: %s", erro)

    logger.info("HTML salvo em: %s", ARQUIVO_DIAGNOSTICO_HTML.resolve())
    logger.info("Screenshot salvo em: %s", ARQUIVO_DIAGNOSTICO_SCREENSHOT.resolve())
    logger.info("Primeiros 1000 caracteres do HTML: %s", limpar_texto(html[:1000]))
    logger.info("Articles encontrados: %s", diagnostico.articles)
    logger.info("Links /p encontrados: %s", diagnostico.links_produto)
    logger.info("Spans com preco: %s", diagnostico.spans_com_preco)
    logger.info('Elementos "no Clube": %s', diagnostico.elementos_clube)
    logger.info("Cards candidatos a produto: %s", diagnostico.cards_candidatos)


def logar_relatorio_diagnostico(diagnostico: DiagnosticoPagina, produtos_extraidos: int) -> None:
    logger.info(
        "\n===== DIAGNOSTICO =====\n"
        "articles encontrados: %s\n"
        "links /p encontrados: %s\n"
        "spans com preco: %s\n"
        'elementos "no Clube": %s\n'
        "cards candidatos: %s\n"
        "produtos extraidos: %s",
        diagnostico.articles,
        diagnostico.links_produto,
        diagnostico.spans_com_preco,
        diagnostico.elementos_clube,
        diagnostico.cards_candidatos,
        produtos_extraidos,
    )


def extrair_preco_por_unidade(textos: list[str]) -> str:
    padrao_unidade = re.compile(
        r"(R\$\s*\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2}).{0,30}/\s*(kg|kilo|quilo|l|lt|litro|litros)",
        re.IGNORECASE,
    )

    for texto in textos:
        if padrao_unidade.search(texto):
            return texto

    for texto in textos:
        texto_lower = texto.lower()
        if any(unidade in texto_lower for unidade in ("/kg", "/ kg", "/l", "/ l", "/lt", "litro")):
            return texto

    return ""


def extrair_desconto(textos: list[str]) -> str:
    for texto in textos:
        if re.search(r"\d+\s*%|off|desconto", texto, re.IGNORECASE):
            return texto
    return ""


def extrair_imagem(card) -> str:
    img = card.find("img")
    if not img:
        return ""

    for atributo in ("src", "data-src", "data-lazy-src", "data-original"):
        valor = img.get(atributo)
        if valor and not valor.startswith("data:image"):
            return urljoin(BASE_URL, valor)

    srcset = img.get("srcset") or img.get("data-srcset") or ""
    if srcset:
        primeira_imagem = srcset.split(",")[0].strip().split(" ")[0]
        return urljoin(BASE_URL, primeira_imagem)

    return ""


def extrair_link(card) -> str:
    if getattr(card, "name", None) == "a" and card.get("href"):
        return urljoin(BASE_URL, card["href"].strip())

    for link_tag in card.find_all("a", href=True):
        href = link_tag["href"].strip()
        if not href or href.startswith("#"):
            continue

        link = urljoin(BASE_URL, href)
        if BASE_URL in link:
            return link

    return ""


def extrair_preco_atual(card) -> Optional[float]:
    preco_tag = card.select_one(SELETOR_PRECO_ATUAL)
    if preco_tag:
        texto_preco = limpar_texto(preco_tag.get_text(" ", strip=True))
        try:
            return limpar_preco(texto_preco)
        except ValueError:
            logger.warning("Nao foi possivel converter preco atual: %s", texto_preco)
            return None

    for elemento in card.find_all(["span", "div", "p"]):
        texto_preco = texto_do_elemento(elemento)
        texto_lower = texto_preco.lower()
        if "R$" not in texto_preco:
            continue
        if "clube" in texto_lower or "/kg" in texto_lower or "/l" in texto_lower or "/lt" in texto_lower:
            continue

        try:
            preco = extrair_primeiro_preco(texto_preco)
            if preco is not None:
                return preco
        except ValueError:
            logger.warning("Nao foi possivel converter preco atual candidato: %s", texto_preco)

    return None


def extrair_preco_clube(card) -> Optional[float]:
    textos_clube = card.find_all(string=re.compile(r"no\s+Clube", re.IGNORECASE))

    for texto_clube in textos_clube:
        elemento = texto_clube.parent
        candidatos = []

        while elemento and elemento != card.parent:
            texto_contexto = limpar_texto(elemento.get_text(" ", strip=True))
            if re.search(r"no\s+Clube", texto_contexto, re.IGNORECASE):
                candidatos.append(texto_contexto)

            if elemento == card:
                break

            elemento = elemento.parent

        for texto_contexto in candidatos:
            clube_match = re.search(r"no\s+Clube", texto_contexto, re.IGNORECASE)
            precos = list(re.finditer(r"R\$\s*\d[\d\s.]*,\s*\d{2}", texto_contexto))

            if not clube_match or not precos:
                continue

            precos_antes_clube = [preco for preco in precos if preco.end() <= clube_match.start()]
            preco_match = precos_antes_clube[-1] if precos_antes_clube else precos[0]

            try:
                return limpar_preco(preco_match.group(0))
            except ValueError:
                logger.warning("Nao foi possivel converter preco Clube: %s", preco_match.group(0))
                return None

    return None


def extrair_produto(nome_tag) -> Optional[Produto]:
    nome = extrair_nome(nome_tag)
    if not nome_parece_produto(nome):
        return None

    card = localizar_bloco_produto(nome_tag)
    if not card:
        return None

    textos = texto_visivel_do_card(card)
    texto_card = " ".join(textos)

    if "R$" not in texto_card:
        return None

    preco_atual = extrair_preco_atual(card)
    preco_clube = extrair_preco_clube(card)
    link = extrair_link(card)

    return Produto(
        nome=nome,
        preco_atual=preco_atual,
        preco_clube=preco_clube,
        preco_por_unidade=extrair_preco_por_unidade(textos),
        desconto=extrair_desconto(textos),
        imagem=extrair_imagem(card),
        link=link,
    )


def extrair_produto_de_card(card) -> Optional[Produto]:
    nome = extrair_nome_do_card(card)
    if not nome_parece_produto(nome):
        return None

    textos = texto_visivel_do_card(card)
    texto_card = " ".join(textos)
    link = extrair_link(card)

    if "R$" not in texto_card or "/p" not in link:
        return None

    preco_atual = extrair_preco_atual(card)
    preco_clube = extrair_preco_clube(card)

    if preco_atual is None and preco_clube is None:
        return None

    return Produto(
        nome=nome,
        preco_atual=preco_atual,
        preco_clube=preco_clube,
        preco_por_unidade=extrair_preco_por_unidade(textos),
        desconto=extrair_desconto(textos),
        imagem=extrair_imagem(card),
        link=link,
    )


def conectar_mysql():
    host = os.getenv("MYSQL_HOST", "127.0.0.1")
    porta = int(os.getenv("MYSQL_PORT", "3306"))
    usuario = os.getenv("MYSQL_USER", "root")
    senha = os.getenv("MYSQL_PASSWORD", "admin")

    logger.info("Conectando ao MySQL em %s:%s.", host, porta)
    conexao = pymysql.connect(
        host=host,
        port=porta,
        user=usuario,
        password=senha,
        charset="utf8mb4",
        autocommit=False,
    )

    with conexao.cursor() as cursor:
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        cursor.execute(f"USE `{DB_NAME}`")
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS `{TABLE_NAME}` (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nomeProduto VARCHAR(255),
                preco DECIMAL(10,2),
                precoClube DECIMAL(10,2),
                link VARCHAR(500),
                dataColeta DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        )

    conexao.commit()
    return conexao


def salvar_produtos(conexao, produtos: list[Produto]) -> int:
    sql = f"""
        INSERT INTO `{TABLE_NAME}` (
            nomeProduto,
            preco,
            precoClube,
            link
        )
        VALUES (%s, %s, %s, %s)
    """

    salvos = 0
    with conexao.cursor() as cursor:
        for produto in produtos:
            try:
                cursor.execute(
                    sql,
                    (
                        produto.nome,
                        produto.preco_atual,
                        produto.preco_clube,
                        produto.link,
                    ),
                )
                salvos += 1
                preco_log = f"R$ {produto.preco_atual:.2f}" if produto.preco_atual is not None else "preco=None"
                preco_clube_log = (
                    f"R$ {produto.preco_clube:.2f}" if produto.preco_clube is not None else "precoClube=None"
                )
                logger.info(
                    "Produto salvo: %s | preco normal: %s | preco Clube: %s",
                    produto.nome,
                    preco_log,
                    preco_clube_log,
                )
            except Exception:
                logger.exception("Erro ao salvar produto: %s", produto.nome)

    conexao.commit()
    return salvos


def raspar_produtos() -> list[Produto]:
    driver = configurar_driver()

    try:
        logger.info("Abrindo site: %s", BASE_URL)
        driver.get(BASE_URL)

        try:
            WebDriverWait(driver, 25).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        except TimeoutException:
            logger.warning("A pagina abriu, mas o body nao apareceu dentro do tempo esperado.")

        aceitar_cookies_se_existir(driver)
        aguardar_produtos_ou_sinais(driver, timeout=60)
        rolar_ate_carregar_tudo(driver)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        nomes_produto = soup.select(SELETOR_NOME_PRODUTO)
        cards_candidatos = encontrar_cards_candidatos(soup)
        diagnostico = gerar_diagnostico(soup, cards_candidatos)
        salvar_diagnostico(driver, soup, diagnostico)

        logger.info("Nomes de produto encontrados no HTML final: %s", len(nomes_produto))
        logger.info("Articles encontrados no HTML final: %s", diagnostico.articles)
        logger.info("Links /p encontrados no HTML final: %s", diagnostico.links_produto)
        logger.info("Spans com preco no HTML final: %s", diagnostico.spans_com_preco)
        logger.info('Elementos "no Clube" no HTML final: %s', diagnostico.elementos_clube)
        logger.info("Cards candidatos no HTML final: %s", diagnostico.cards_candidatos)

        produtos: list[Produto] = []
        chaves_vistas: set[tuple[str, str]] = set()

        def adicionar_produto(produto: Optional[Produto]) -> None:
            if not produto:
                return

            chave = (produto.nome.lower(), produto.link)
            if chave in chaves_vistas:
                return

            chaves_vistas.add(chave)
            produtos.append(produto)
            logger.info(
                "Produto extraido: %s | preco normal=%s | preco Clube=%s",
                produto.nome,
                produto.preco_atual,
                produto.preco_clube,
            )

        for nome_tag in nomes_produto:
            try:
                adicionar_produto(extrair_produto(nome_tag))
            except Exception:
                logger.exception("Erro ao extrair um card de produto.")

        if cards_candidatos:
            logger.info("Usando cards candidatos descobertos para complementar a extracao.")
            for card in cards_candidatos:
                try:
                    adicionar_produto(extrair_produto_de_card(card))
                except Exception:
                    logger.exception("Erro ao extrair um card candidato de produto.")

        logger.info("Produtos validos extraidos: %s", len(produtos))
        logar_relatorio_diagnostico(diagnostico, len(produtos))
        return produtos
    finally:
        driver.quit()
        logger.info("Navegador fechado.")


def main() -> None:
    conexao = None

    try:
        produtos = raspar_produtos()
        if not produtos:
            logger.warning("Nenhum produto foi encontrado para salvar.")
            return

        conexao = conectar_mysql()
        total_salvo = salvar_produtos(conexao, produtos)
        logger.info("Processo concluido. Produtos salvos/atualizados: %s", total_salvo)
    except Exception:
        logger.exception("Erro geral na execucao do scraper.")
    finally:
        if conexao:
            conexao.close()
            logger.info("Conexao MySQL fechada.")


if __name__ == "__main__":
    main()
