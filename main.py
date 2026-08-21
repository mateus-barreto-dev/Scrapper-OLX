import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from buscador_olx import extrair_links_pagina_busca
from scraper_teste import extrair_anuncio_olx
from avaliador_ia import analisar_anuncio_com_gemini
from gerenciador_excel import (
    inicializar_planilha,
    anuncio_ja_analisado,
    salvar_analise_excel,
    obter_melhores_oportunidades
)

URL_LISTAGEM_OLX = "https://www.olx.com.br/informatica/notebooks/estado-se"

# No plano Free Tier, mantenha 1 thread para evitar estourar limites por segundo/minuto
MAX_THREADS = 1 
DELAY_ENTRE_REQUISICOES = 3  # segundos de pausa entre chamadas da IA

def processar_anuncio_individual(args):
    idx, total, url = args

    if anuncio_ja_analisado(url):
        return {"status": "IGNORADO", "url": url}

    print(f"[{idx}/{total}] Processando: {url}")

    try:
        dados_scraper = extrair_anuncio_olx(url)

        # OPTIONAL: Filtro local simples antes de gastar cota da IA
        # Exemplo: Ignorar se nao tiver preco ou for acima de um limite
        preco = dados_scraper.get("preco_numerico", 0)
        if preco <= 0 or preco > 10000:
            print(" -> Ignorado pelo filtro de preco local (economizando IA).")
            return {"status": "FILTRADO", "url": url}

        print(" -> Enviando para avaliacao do Gemini 3.5...")
        dados_ia = analisar_anuncio_com_gemini(dados_scraper)

        time.sleep(DELAY_ENTRE_REQUISICOES)

        if dados_ia:
            salvar_analise_excel(dados_scraper, dados_ia)
            return {
                "status": "SUCESSO",
                "titulo": dados_scraper["titulo"],
                "veredito": dados_ia.get("veredito"),
                "nota": dados_ia.get("nota_oportunidade"),
                "url": url
            }
        else:
            return {"status": "ERRO_IA", "url": url}

    except Exception as e:
        print(f"Erro ao processar {url}: {e}")
        return {"status": "ERRO", "url": url}

def executar_varredura():
    print("="*60)
    print(" INICIANDO VARREDURA CONTROLADA OLX (GEMINI 3.5)")
    print("="*60)

    inicializar_planilha()

    links = extrair_links_pagina_busca(URL_LISTAGEM_OLX)
    if not links:
        print("Nenhum anuncio encontrado.")
        return

    # Limita o lote por execucao ao tamanho da cota diária (ex: 15 para ter margem)
    LIMITE_LOTE_DIARIO = 15
    links_para_processar = links[:LIMITE_LOTE_DIARIO]

    print(f"\nTotal de links na pagina: {len(links)}")
    print(f"Processando lote seguro de {len(links_para_processar)} anuncios nesta rodada...\n")

    tarefas = [(idx, len(links_para_processar), url) for idx, url in enumerate(links_para_processar, 1)]
    resultados = []

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = [executor.submit(processar_anuncio_individual, tarefa) for tarefa in tarefas]

        for future in as_completed(futures):
            res = future.result()
            resultados.append(res)

    sucessos = sum(1 for r in resultados if r["status"] == "SUCESSO")
    ignorados = sum(1 for r in resultados if r["status"] in ["IGNORADO", "FILTRADO"])
    erros = sum(1 for r in resultados if "ERRO" in r["status"])

    print("\n" + "="*60)
    print(" RESUMO DA VARREDURA:")
    print(f" -> Processados com sucesso: {sucessos}")
    print(f" -> Ignorados (Existentes/Filtro): {ignorados}")
    print(f" -> Falhas/Erros de cota: {erros}")
    print("="*60)

if __name__ == "__main__":
    executar_varredura()