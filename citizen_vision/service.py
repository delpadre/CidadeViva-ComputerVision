# Camada de serviço: bytes de uma imagem -> resposta (dicionário) para o MVP.
# É usada pela API (api.py) e pelo servidor de demonstração (demo_server.py).

import cv2
import numpy as np

from .municipio import resolve_municipio
from .pipeline import process_image


# --------------------------------------------------
# CONFIGURAÇÕES
# --------------------------------------------------

# Tamanho máximo da imagem enviada: 8 MB
MAX_BYTES = 8 * 1024 * 1024


class ServiceError(Exception):
    # Erro com um código HTTP (400, 413, 503, 500) e uma mensagem para mostrar ao usuário.
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def extract_from_bytes(dados, lookup_ibge=False):
    # Tudo é processado em memória: nada é gravado em disco nem registrado em log (LGPD).

    # 1. Conferir o arquivo recebido
    if not dados:
        raise ServiceError(400, "nenhuma imagem enviada")
    if len(dados) > MAX_BYTES:
        raise ServiceError(413, "imagem maior que 8 MB")

    imagem = cv2.imdecode(np.frombuffer(dados, np.uint8), cv2.IMREAD_COLOR)
    if imagem is None:
        raise ServiceError(400, "arquivo não é uma imagem válida")

    # 2. Rodar o pipeline
    try:
        resultado = process_image(imagem)
    except Exception as erro:
        # Caso mais comum: o Tesseract não está instalado ou não está no PATH
        if type(erro).__name__ == "TesseractNotFoundError":
            raise ServiceError(503, "OCR indisponível no servidor: instale o Tesseract (com idioma português) e reinicie")
        raise ServiceError(500, "falha ao processar a imagem")

    resposta = resultado.to_dict()

    # 3. Município: só informamos se a cidade lida parece confiável.
    # Se a cidade veio errada, mostrar um município falso seria pior do que não mostrar.
    cidade_confiavel = bool(resultado.address) and "cidade" not in resultado.fields_to_check

    if cidade_confiavel:
        resposta["municipio"] = resolve_municipio(resultado.address, online=lookup_ibge)
    else:
        resposta["municipio"] = None

    # 4. Se o CEP aponta para outra cidade, avisar para o cidadão conferir
    if resposta["municipio"] and resposta["municipio"]["confere_cep"] is False:
        resposta["warnings"].append("CEP não confere com a cidade da fatura")

    return resposta
