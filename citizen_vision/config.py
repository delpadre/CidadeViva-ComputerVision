# Configuração de cada empresa e utilidades de texto.
#
# Para ADICIONAR uma empresa nova, basta incluí-la em COMPANIES:
#   keywords -> palavras que só aparecem nas contas dela (usadas para reconhecer a empresa)
#   anchor   -> o rótulo que vem logo antes do endereço CORRETO (sem acento e em maiúsculas)
#   layout   -> como o endereço está escrito: "multiline", "street_bairro" ou "inline"
#               (cada um tem um leitor em extract.py)

import re
import unicodedata


def normalize(texto):
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(letra for letra in texto if not unicodedata.combining(letra))   # tira os acentos

    texto = texto.replace("–", "-").replace("—", "-").replace("_", " ")
    texto = re.sub(r"\s+", " ", texto.upper())

    return texto.strip()


UFS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG",
    "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}


class Company:
    def __init__(self, key, display, keywords, anchor, layout):
        self.key = key
        self.display = display
        self.keywords = keywords
        self.anchor = anchor
        self.layout = layout


COMPANIES = {
    "enel": Company(
        "enel",
        "Enel (energia)",
        ("ENEL", "ENERGIA ELETRICA", "UNIDADE CONSUMIDORA", "KWH"),
        "ENDERECO DA UNIDADE CONSUMIDORA",
        "multiline",
    ),
    "sabesp": Company(
        "sabesp",
        "Sabesp (água)",
        ("SABESP", "AGUA E ESGOTO", "HIDROMETRO", "ESGOTO"),
        "ENDERECO DO IMOVEL",
        "street_bairro",
    ),
    "claro": Company(
        "claro",
        "Claro (telecom)",
        ("CLARO", "INTERNET", "FATURA CLARO", "MBPS"),
        "ENDERECO DE ENTREGA DA FATURA",
        "inline",
    ),
}


# Rótulos de endereços que NÃO queremos (cobrança, sede).
# Servem de "pare": quando a leitura chega num deles, o endereço certo já acabou.
DECOY_LABELS = ("ENDERECO DE COBRANCA", "ENDERECO DA SEDE", "SEDE")
