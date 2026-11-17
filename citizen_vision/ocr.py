# Etapa 3: OCR (leitura do texto), agrupado em linhas com confiança e posição.

import numpy as np
import pytesseract


class Line:
    # Uma linha de texto lida pelo OCR.
    #   text -> o texto da linha
    #   conf -> confiança média do Tesseract nessa linha (0 a 100)
    #   box  -> posição na imagem: (x0, y0, x1, y1)
    def __init__(self, text, conf, box):
        self.text = text
        self.conf = conf
        self.box = box


def pick_lang():
    # Usa português + inglês se o pacote de idioma "por" estiver instalado.
    # Se não estiver (ou se o Tesseract não responder), cai para inglês.
    try:
        idiomas = set(pytesseract.get_languages(config=""))
    except Exception:
        return "eng"

    if "por" in idiomas:
        return "por+eng"
    return "eng"


def ocr_lines(imagem, lang=None, psm=6):
    # psm 6 = "um bloco de texto com linhas uniformes". Funciona bem em contas.
    if lang is None:
        lang = pick_lang()

    dados = pytesseract.image_to_data(
        imagem,
        lang=lang,
        config=f"--psm {psm}",
        output_type=pytesseract.Output.DICT,
    )

    # 1. Agrupar as palavras por linha.
    # O Tesseract identifica cada palavra por (bloco, parágrafo, linha).
    grupos = {}
    for i in range(len(dados["text"])):
        palavra = dados["text"][i].strip()
        confianca = float(dados["conf"][i])

        if not palavra or confianca < 0:   # conf -1 = não é uma palavra de verdade
            continue

        chave = (dados["block_num"][i], dados["par_num"][i], dados["line_num"][i])
        grupos.setdefault(chave, []).append(i)

    # 2. Montar cada linha: texto, confiança média e caixa
    linhas = []
    for indices in grupos.values():
        indices.sort(key=lambda i: dados["left"][i])   # palavras da esquerda para a direita

        texto = " ".join(dados["text"][i] for i in indices)
        confianca = float(np.mean([float(dados["conf"][i]) for i in indices]))

        x0 = min(dados["left"][i] for i in indices)
        y0 = min(dados["top"][i] for i in indices)
        x1 = max(dados["left"][i] + dados["width"][i] for i in indices)
        y1 = max(dados["top"][i] + dados["height"][i] for i in indices)

        linhas.append(Line(texto, confianca, (x0, y0, x1, y1)))

    # 3. Ordenar de cima para baixo (e da esquerda para a direita)
    linhas.sort(key=lambda linha: (linha.box[1], linha.box[0]))

    return linhas
