# Pipeline completo: foto -> empresa + endereço em campos + sinal de revisão.
#
# Etapas:
#   1. Endireitar a folha         (document.py)
#   2. Limpar a imagem            (preprocess.py)
#   3. Ler o texto (OCR)          (ocr.py)
#   4. Descobrir a empresa        (classify.py)
#   5. Achar o endereço certo     (extract.py)
#   6. Validar os campos          (validate.py)

import os
import time

import cv2
import numpy as np

from .classify import classify_company
from .document import rectify
from .extract import extract_address
from .ocr import ocr_lines
from .preprocess import preprocess
from .validate import check_fields


# --------------------------------------------------
# CONFIGURAÇÕES
# --------------------------------------------------

# Se a confiança média do OCR ficar abaixo disso (0 a 1), avisamos "baixa confiança".
LIMITE_CONFIANCA = 0.70


class ExtractionResult:
    # O resultado do pipeline. Cada atributo vira uma chave do JSON da API.
    def __init__(self):
        self.company = None            # "enel", "sabesp", "claro" ou None
        self.company_confidence = 0.0
        self.document_found = False    # achou os cantos da folha?
        self.address = {}              # logradouro, numero, bairro, cidade, uf, cep
        self.address_lines = []        # as linhas de texto de onde o endereço saiu
        self.ocr_confidence = 0.0
        self.warnings = []             # avisos em texto
        self.fields_to_check = []      # campos que o cidadão deve conferir com atenção
        self.needs_review = True       # sempre True: o cidadão SEMPRE confirma (humano no circuito)
        self.timings_ms = {}           # tempo de cada etapa, em milissegundos

    def to_dict(self):
        return dict(self.__dict__)


def _load(imagem):
    # Aceita um caminho de arquivo ou uma imagem já carregada (array do OpenCV).
    if isinstance(imagem, np.ndarray):
        return imagem

    carregada = cv2.imread(str(imagem))
    if carregada is None:
        raise ValueError(f"não foi possível ler a imagem: {imagem}")
    return carregada


def process_image(imagem, lang=None, debug_dir=None):
    # `imagem`: caminho do arquivo ou array BGR.
    # Não grava nada em disco, a não ser que `debug_dir` seja informado (modo de depuração).
    res = ExtractionResult()
    inicio = time.perf_counter()
    imagem = _load(imagem)

    # 1. Endireitar a folha
    folha, res.document_found = rectify(imagem)
    depois_de_endireitar = time.perf_counter()

    # 2. Limpar a imagem
    preparada = preprocess(folha)
    depois_de_limpar = time.perf_counter()

    # 3. Ler o texto
    linhas = ocr_lines(preparada["enhanced"], lang=lang)
    depois_do_ocr = time.perf_counter()

    # 4. Descobrir a empresa
    res.company, res.company_confidence = classify_company(linhas)

    if res.company is None:
        res.warnings.append("empresa não reconhecida")
    else:
        # 5. Achar o endereço certo
        res.address, res.address_lines, res.ocr_confidence = extract_address(linhas, res.company)

        if not res.address:
            res.warnings.append("rótulo do endereço não encontrado")
        else:
            # 6. Validar os campos
            avisos, res.fields_to_check = check_fields(res.address)
            res.warnings += avisos

    # Avisos gerais
    if not res.document_found:
        res.warnings.append("bordas do documento não detectadas (usando imagem inteira)")

    if res.ocr_confidence and res.ocr_confidence < LIMITE_CONFIANCA:
        res.warnings.append("baixa confiança do OCR")

    # Tempo de cada etapa, em milissegundos
    res.timings_ms = {
        "retificacao": round((depois_de_endireitar - inicio) * 1000),
        "preprocessamento": round((depois_de_limpar - depois_de_endireitar) * 1000),
        "ocr": round((depois_do_ocr - depois_de_limpar) * 1000),
        "total": round((time.perf_counter() - inicio) * 1000),
    }

    # Modo de depuração: salva as imagens de cada etapa para você ver o que o OCR enxergou
    if debug_dir:
        os.makedirs(debug_dir, exist_ok=True)
        cv2.imwrite(os.path.join(debug_dir, "1_retificada.png"), folha)
        cv2.imwrite(os.path.join(debug_dir, "2_ocr_input.png"), preparada["enhanced"])
        cv2.imwrite(os.path.join(debug_dir, "3_binaria.png"), preparada["binary"])

    return res
