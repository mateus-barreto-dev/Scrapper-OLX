import os
import threading
from datetime import datetime
import pandas as pd

NOME_ARQUIVO_EXCEL = "anuncios_analisados.xlsx"
EXCEL_LOCK = threading.Lock()  # Mutex para proteger leituras e escritas concorrentes

COLUNAS = [
    "data_analise",
    "id_anuncio",
    "titulo",
    "preco_numerico",
    "preco_bruto",
    "veredito",
    "nota_oportunidade",
    "faixa_preco_estimada",
    "resumo_executivo",
    "pontos_positivos",
    "red_flags",
    "url"
]


def extrair_id_url(url):
    try:
        url_limpa = url.split("?")[0]
        return url_limpa.rstrip("/").split("-")[-1]
    except Exception:
        return url


def inicializar_planilha():
    with EXCEL_LOCK:
        if not os.path.exists(NOME_ARQUIVO_EXCEL):
            df = pd.DataFrame(columns=COLUNAS)
            df.to_excel(NOME_ARQUIVO_EXCEL, index=False, engine="openpyxl")
            print(f"Planilha '{NOME_ARQUIVO_EXCEL}' criada com sucesso.")


def anuncio_ja_analisado(url_anuncio):
    id_anuncio = extrair_id_url(url_anuncio)

    with EXCEL_LOCK:
        if not os.path.exists(NOME_ARQUIVO_EXCEL):
            return False

        try:
            df = pd.read_excel(NOME_ARQUIVO_EXCEL, engine="openpyxl")
            if not df.empty and "id_anuncio" in df.columns:
                ids_existentes = df["id_anuncio"].astype(str).tolist()
                return str(id_anuncio) in ids_existentes
        except Exception as e:
            print(f"Erro ao verificar duplicidade na planilha: {e}")

    return False


def salvar_analise_excel(dados_scraper, dados_ia):
    id_anuncio = extrair_id_url(dados_scraper["url"])
    data_atual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    nova_linha = {
        "data_analise": data_atual,
        "id_anuncio": id_anuncio,
        "titulo": dados_scraper["titulo"],
        "preco_numerico": dados_scraper["preco_numerico"],
        "preco_bruto": dados_scraper["preco_bruto"],
        "veredito": dados_ia.get("veredito", "N/A"),
        "nota_oportunidade": dados_ia.get("nota_oportunidade", 0.0),
        "faixa_preco_estimada": dados_ia.get("faixa_preco_estimada_mercado", "N/A"),
        "resumo_executivo": dados_ia.get("resumo_executivo", "N/A"),
        "pontos_positivos": " | ".join(dados_ia.get("pontos_positivos", [])),
        "red_flags": " | ".join(dados_ia.get("red_flags_alertas", [])),
        "url": dados_scraper["url"]
    }

    # Bloqueia a regiao critica para escrita exclusiva no arquivo
    with EXCEL_LOCK:
        try:
            if os.path.exists(NOME_ARQUIVO_EXCEL):
                df_existente = pd.read_excel(NOME_ARQUIVO_EXCEL, engine="openpyxl")
            else:
                df_existente = pd.DataFrame(columns=COLUNAS)

            df_novo = pd.DataFrame([nova_linha])
            df_final = pd.concat([df_existente, df_novo], ignore_index=True)

            df_final.to_excel(NOME_ARQUIVO_EXCEL, index=False, engine="openpyxl")
            print(f" -> Anúncio ID {id_anuncio} gravado com sucesso no Excel.")
        except Exception as e:
            print(f"Erro ao salvar dados no Excel: {e}")


def obter_melhores_oportunidades(nota_minima=7.0):
    with EXCEL_LOCK:
        if not os.path.exists(NOME_ARQUIVO_EXCEL):
            return None

        try:
            df = pd.read_excel(NOME_ARQUIVO_EXCEL, engine="openpyxl")
            if df.empty:
                return None

            vereditos_validos = ["EXCELENTE_OPORTUNIDADE", "PRECO_JUSTO"]
            filtro = (df["veredito"].isin(vereditos_validos)) & (df["nota_oportunidade"] >= nota_minima)

            return df[filtro].sort_values(by="nota_oportunidade", ascending=False)
        except Exception as e:
            print(f"Erro ao ler oportunidades do Excel: {e}")
            return None