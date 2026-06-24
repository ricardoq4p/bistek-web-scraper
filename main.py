import logging
import os
import re
import time
from dataclasses import dataclass
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
    preco_por_unidade: str
    desconto: str
    imagem: str
    link: str


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


def rolar_ate_carregar_tudo(driver: webdriver.Chrome, pausa: float = 2.0, limite_sem_mudanca: int = 5) -> None:
    logger.info("Rolando a pagina para carregar todos os produtos.")

    altura_anterior = 0
    qtd_nomes_anterior = 0
    tentativas_sem_mudanca = 0

    while tentativas_sem_mudanca < limite_sem_mudanca:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pausa)

        altura_atual = driver.execute_script("return document.body.scrollHeight")
        qtd_nomes_atual = len(driver.find_elements(By.CSS_SELECTOR, SELETOR_NOME_PRODUTO))

        logger.info(
            "Scroll realizado | altura=%s | nomes de produto=%s",
            altura_atual,
            qtd_nomes_atual,
        )

        if altura_atual == altura_anterior and qtd_nomes_atual == qtd_nomes_anterior:
            tentativas_sem_mudanca += 1
        else:
            tentativas_sem_mudanca = 0

        altura_anterior = altura_atual
        qtd_nomes_anterior = qtd_nomes_atual

    logger.info("Scroll concluido. Nenhum novo produto apareceu nas ultimas tentativas.")


def texto_visivel_do_card(card) -> list[str]:
    return [limpar_texto(texto) for texto in card.stripped_strings if limpar_texto(texto)]


def extrair_nome(nome_tag) -> str:
    return limpar_texto(nome_tag.get("title") or nome_tag.get_text(" ", strip=True))


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
    if not preco_tag:
        return None

    texto_preco = limpar_texto(preco_tag.get_text(" ", strip=True))
    try:
        return limpar_preco(texto_preco)
    except ValueError:
        logger.warning("Nao foi possivel converter preco atual: %s", texto_preco)
        return None


def extrair_produto(nome_tag) -> Optional[Produto]:
    nome = extrair_nome(nome_tag)
    if not nome:
        return None

    card = localizar_bloco_produto(nome_tag)
    if not card:
        return None

    textos = texto_visivel_do_card(card)
    texto_card = " ".join(textos)

    if "R$" not in texto_card:
        return None

    preco_atual = extrair_preco_atual(card)
    link = extrair_link(card)

    return Produto(
        nome=nome,
        preco_atual=preco_atual,
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
                precoPorUnidade VARCHAR(50),
                desconto VARCHAR(20),
                link VARCHAR(500),
                imagem VARCHAR(500),
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
            precoPorUnidade,
            desconto,
            link,
            imagem
        )
        VALUES (%s, %s, %s, %s, %s, %s)
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
                        produto.preco_por_unidade,
                        produto.desconto,
                        produto.link,
                        produto.imagem,
                    ),
                )
                salvos += 1
                preco_log = f"R$ {produto.preco_atual:.2f}" if produto.preco_atual is not None else "preco=None"
                logger.info("Produto salvo: %s | %s", produto.nome, preco_log)
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
            WebDriverWait(driver, 25).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, SELETOR_NOME_PRODUTO))
            )
        except TimeoutException:
            logger.warning("A pagina abriu, mas nenhum nome de produto apareceu dentro do tempo esperado.")

        aceitar_cookies_se_existir(driver)
        rolar_ate_carregar_tudo(driver)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        nomes_produto = soup.select(SELETOR_NOME_PRODUTO)
        logger.info("Nomes de produto encontrados no HTML final: %s", len(nomes_produto))

        produtos: list[Produto] = []
        chaves_vistas: set[tuple[str, str]] = set()

        for nome_tag in nomes_produto:
            try:
                produto = extrair_produto(nome_tag)
                if not produto:
                    continue

                chave = (produto.nome.lower(), produto.link)
                if chave in chaves_vistas:
                    continue

                chaves_vistas.add(chave)
                produtos.append(produto)
                logger.info("Produto extraido: %s", produto.nome)
            except Exception:
                logger.exception("Erro ao extrair um card de produto.")

        logger.info("Produtos validos extraidos: %s", len(produtos))
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
