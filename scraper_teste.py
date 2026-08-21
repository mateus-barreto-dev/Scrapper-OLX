import os
import re
from playwright.sync_api import sync_playwright

def extrair_anuncio_olx(url_anuncio):
    print(f" Acessando anúncio: {url_anuncio}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()

        try:
            page.goto(url_anuncio, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(2500)

            # Rola a página para carregar dinamicamente o DOM
            page.evaluate("window.scrollTo(0, 600);")
            page.wait_for_timeout(1000)

            # --- 1. Extração do Título (Blindada contra Preços) ---
            titulo = "Título não encontrado"
            try:
                # Prioridade 1: TestID ou ID oficial de título do anúncio
                if page.locator("[data-testid='ad-title']").count() > 0:
                    titulo = page.locator("[data-testid='ad-title']").first.inner_text().strip()
                elif page.locator("#ad-title").count() > 0:
                    titulo = page.locator("#ad-title").first.inner_text().strip()
                elif page.locator("h1").count() > 0:
                    cand = page.locator("h1").first.inner_text().strip()
                    if "R$" not in cand:
                        titulo = cand

                # Prioridade 2: Busca por tipografia de título no topo que NÃO seja preço
                if titulo == "Título não encontrado":
                    titulos_candidatos = page.locator("span[class*='typo-title-medium'], h1, h2").all()
                    for cand in titulos_candidatos:
                        txt = cand.inner_text().strip()
                        # Ignora preços, palavras do sistema e textos curtos
                        if txt and "R$" not in txt and len(txt) > 8 and txt not in ["Detalhes", "Localização", "Descrição"]:
                            titulo = txt
                            break
            except Exception as e:
                print(f" Alerta no título: {e}")

            # --- 2. Extração Precisa do Preço ---
            preco_raw = "N/A"
            preco_numerico = 0.0
            try:
                container_preco = page.locator("#price-box-container")
                
                # Busca pelo valor principal em destaque
                if container_preco.locator("[class*='typo-title-large']").count() > 0:
                    preco_raw = container_preco.locator("[class*='typo-title-large']").first.inner_text().strip()
                else:
                    spans = container_preco.locator("span, p, div").all()
                    for s in spans:
                        txt = s.inner_text().strip()
                        style = s.get_attribute("style") or ""
                        if "R$" in txt and "line-through" not in style and "OFF" not in txt and "sem juros" not in txt:
                            match = re.search(r"R\$\s?[\d\.]+", txt)
                            if match:
                                preco_raw = match.group(0)
                                break

                preco_numerico = float(re.sub(r"[^\d]", "", preco_raw)) if preco_raw != "N/A" else 0.0
            except Exception as e:
                print(f" Alerta no preço: {e}")

            # --- 3. Extração da Descrição Completa ---
            descricao = "Descrição não encontrada"
            try:
                btn_desc = page.get_by_role("button", name="Ver descrição completa")
                if btn_desc.is_visible():
                    btn_desc.click(force=True)
                    page.wait_for_timeout(400)

                paragrafos = page.locator("p, span, div").all_inner_texts()
                textos_validos = []

                for txt in paragrafos:
                    t = txt.strip()
                    if len(t) > 80 and not any(k in t for k in ["Pague online", "Garantia da OLX", "Ir para o menu", "Plano Profissional"]):
                        if t not in textos_validos:
                            textos_validos.append(t)

                if textos_validos:
                    descricao_bruta = max(textos_validos, key=len)
                    
                    # Remove o excesso e botões do rodapé da descrição
                    for termo_corte in ["publicidade", "\nDetalhes\n", "Detalhes\nCategoria", "Ver descrição completa"]:
                        if termo_corte in descricao_bruta:
                            descricao_bruta = descricao_bruta.split(termo_corte)[0]

                    if descricao_bruta.startswith(titulo):
                        descricao = descricao_bruta[len(titulo):].strip()
                    else:
                        descricao = descricao_bruta.strip()
            except Exception as e:
                print(f" Alerta na descrição: {e}")

            # --- 4. Extração Genérica da Ficha Técnica (#details) ---
            detalhes = {}
            try:
                btn_ver_mais = page.get_by_role("button", name="Ver mais")
                if btn_ver_mais.is_visible():
                    btn_ver_mais.click(force=True)
                    page.wait_for_timeout(400)

                if page.locator("#details").count() > 0:
                    texto_bruto = page.locator("#details").inner_text()
                    linhas = [l.strip() for l in texto_bruto.split("\n") if l.strip()]
                    
                    linhas_filtradas = [
                        l for l in linhas 
                        if l not in ["Detalhes", "Ver mais", "Fechar janela de diálogo", "ou"]
                    ]

                    idx = 0
                    while idx < len(linhas_filtradas):
                        item = linhas_filtradas[idx]
                        
                        if item == "Características" and (idx + 1) < len(linhas_filtradas):
                            detalhes["Características"] = linhas_filtradas[idx + 1]
                            idx += 2
                        elif (idx + 1) < len(linhas_filtradas):
                            chave = item
                            valor = linhas_filtradas[idx + 1]
                            if len(chave) < 40 and chave not in detalhes:
                                detalhes[chave] = valor
                            idx += 2
                        else:
                            idx += 1
            except Exception as e:
                print(f" Alerta nos detalhes: {e}")

            page.keyboard.press("Escape")

            # --- 5. Download de Fotos ---
            caminhos_fotos = []
            try:
                os.makedirs(".temp", exist_ok=True)
                page.evaluate("window.scrollTo(0, 0);")
                page.wait_for_timeout(500)

                todas_imgs = page.locator("img").all()
                urls_unicas = set()

                for img in todas_imgs:
                    src = img.get_attribute("src") or img.get_attribute("data-src")
                    if src and ("olx" in src or "images" in src) and ("http" in src):
                        if "static" not in src and "avatar" not in src and "icon" not in src:
                            urls_unicas.add(src.split("?")[0])

                for idx, img_url in enumerate(list(urls_unicas)[:6], 1):
                    caminho_foto = os.path.join(".temp", f"foto_{idx}.jpg")
                    response = page.request.get(img_url)
                    with open(caminho_foto, "wb") as f:
                        f.write(response.body())
                    caminhos_fotos.append(caminho_foto)

            except Exception as e:
                print(f" Erro ao baixar fotos: {e}")

            return {
                "titulo": titulo,
                "preco_bruto": preco_raw,
                "preco_numerico": preco_numerico,
                "descricao": descricao,
                "detalhes": detalhes,
                "fotos": caminhos_fotos,
                "url": url_anuncio
            }

        finally:
            browser.close()

if __name__ == "__main__":
    # Teste com o MacBook M3
    URL_TESTE = "https://se.olx.com.br/sergipe/informatica/notebooks/notebook-gamer-msi-katana-gf66-i7-rtx-3060-64gb-ssd-2tb-144hz-1510709135?lis=listing_19020" 
    
    print("🚀 Testando Scraper Ajustado para Título...")
    resultado = extrair_anuncio_olx(URL_TESTE)
    
    print("\n" + "="*50)
    print("--- RESULTADO FINAL DA EXTRAÇÃO ---")
    print("="*50)
    print(f" Título: {resultado['titulo']}")
    print(f" Preço: {resultado['preco_bruto']} (R$ {resultado['preco_numerico']})")
    print(f" Fotos Baixadas: {len(resultado['fotos'])} foto(s)")
    
    print("\n Ficha Técnica (Detalhes):")
    if resultado['detalhes']:
        for k, v in resultado['detalhes'].items():
            print(f"  • {k}: {v}")
    else:
        print("  (Nenhum detalhe encontrado)")

    print(f"\n Descrição:\n{resultado['descricao']}")