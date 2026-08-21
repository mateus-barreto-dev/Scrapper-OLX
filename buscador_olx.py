import re
import json
import cloudscraper
from bs4 import BeautifulSoup

def extrair_links_pagina_busca(url_busca):
    """
    Recebe a URL de uma listagem/busca da OLX e retorna a lista de links dos anuncios encontrados.
    Utiliza cloudscraper para contornar bloqueios 403 do Cloudflare.
    """
    links = []
    print(f"Buscando lista de anuncios em: {url_busca}")

    try:
        # Inicializa o scraper que simula navegadores reais
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )

        response = scraper.get(url_busca, timeout=20)

        if response.status_code != 200:
            print(f"Erro ao acessar pagina de busca. Status HTTP: {response.status_code}")
            return links

        soup = BeautifulSoup(response.text, "html.parser")

        # METODO 1: Extraçao via JSON embutido (__NEXT_DATA__)
        script_json = soup.find("script", id="__NEXT_DATA__")
        if script_json and script_json.string:
            try:
                data = json.loads(script_json.string)
                page_props = data.get("props", {}).get("pageProps", {})
                
                # Tenta localizar a lista de anuncios dentro do JSON
                ads_list = page_props.get("ads", []) or page_props.get("listProps", {}).get("ads", [])

                for ad in ads_list:
                    url_anuncio = ad.get("url") or ad.get("subjectUrl")
                    if url_anuncio and url_anuncio not in links:
                        links.append(url_anuncio)

                if links:
                    print(f"Extraidos {len(links)} links via dados estruturados (JSON).")
                    return links
            except Exception as e:
                print(f"Aviso: Nao foi possivel extrair pelo JSON ({e}). Tentando fallback HTML...")

        # METODO 2: Fallback via varredura de tags HTML (DOM)
        cards = soup.find_all("a", href=True)
        for card in cards:
            href = card["href"]
            # Filtra apenas links de anuncios individuais (contendo o ID numerico da OLX)
            if "olx.com.br" in href and re.search(r'-\d+(\?|$)', href):
                link_limpo = href.split("?")[0]
                if link_limpo not in links:
                    links.append(link_limpo)

        print(f"Extraidos {len(links)} links via tags HTML.")
        return links

    except Exception as e:
        print(f"Erro no processamento da busca: {e}")
        return links


if __name__ == "__main__":
    URL_TESTE = "https://www.olx.com.br/informatica/notebooks/estado-se"
    resultado = extrair_links_pagina_busca(URL_TESTE)
    print(f"\nTotal de anuncios encontrados: {len(resultado)}")
    for idx, link in enumerate(resultado[:5], 1):
        print(f"{idx}. {link}")