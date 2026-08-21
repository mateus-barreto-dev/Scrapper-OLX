import os
import json
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image
from json_repair import repair_json

load_dotenv()

API_KEYS = [os.getenv("GEMINI_API_KEY_1")]
API_KEYS = [k for k in API_KEYS if k]

def analisar_anuncio_com_gemini(dados_anuncio, max_retries=3):
    if not API_KEYS:
        print("Erro: Nenhuma GEMINI_API_KEY configurada.")
        return None

    prompt = f"""
    Voce e um especialista em precificacao, hardware e avaliacao de notebooks seminovos e usados no Brasil.
    Analise os dados extraidos de um anuncio da OLX e as imagens em anexo para emitir um parecer preciso de compra.

    TITULO: {dados_anuncio['titulo']}
    PRECO SOLICITADO: {dados_anuncio['preco_bruto']}
    FICHA TECNICA: {json.dumps(dados_anuncio['detalhes'], ensure_ascii=False)}
    DESCRICAO DO VENDEDOR:
    {dados_anuncio['descricao']}

    INSTRUCOES DE ANALISE:
    1. Verifique se o preco esta abaixo, na media ou acima do valor de mercado.
    2. Avalie as imagens anexadas procurando por marcas de impacto ou defeitos.
    3. Identifique na descricao se ha alerta sobre bateria, tela, teclado ou defeitos.

    Retorne APENAS um objeto JSON valido seguindo a estrutura:
    {{
      "veredito": "EXCELENTE_OPORTUNIDADE" | "PRECO_JUSTO" | "NAO_RECOMENDADO" | "RISCO_ALTO_DE_FRAUDE",
      "nota_oportunidade": 8.5,
      "faixa_preco_estimada_mercado": "R$ X.XXX a R$ X.XXX",
      "pontos_positivos": ["item 1"],
      "red_flags_alertas": ["item 1"],
      "resumo_executivo": "Texto corrido sem aspas internas."
    }}
    """

    imagens_pil = []
    for foto_path in dados_anuncio.get("fotos", []):
        if os.path.exists(foto_path):
            try:
                img = Image.open(foto_path)
                imagens_pil.append(img)
            except Exception as e:
                pass

    conteudo_request = [prompt] + imagens_pil

    for idx, key in enumerate(API_KEYS, 1):
        client = genai.Client(api_key=key)

        for tentativa in range(1, max_retries + 1):
            try:
                response = client.models.generate_content(
                    model='gemini-3.5-flash',
                    contents=conteudo_request,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.1
                    )
                )

                string_json_corrigida = repair_json(response.text)
                return json.loads(string_json_corrigida)

            except Exception as e:
                erro_str = str(e)
                if "503" in erro_str or "429" in erro_str or "UNAVAILABLE" in erro_str:
                    if tentativa < max_retries:
                        print(f" -> AVISO: Gemini indisponivel temporariamente (Erro 503/429). Tentando novamente ({tentativa}/{max_retries})...")
                        time.sleep(2 * tentativa) # Pausa progressiva
                        continue
                print(f"Erro na IA: {e}")
                break

    return None