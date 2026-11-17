# Etapa 5: achar o endereço CORRETO (a fatura tem vários) e separar em campos.
#
# Ideia: cada empresa escreve o endereço do imóvel depois de um rótulo fixo
# (ex.: "ENDERECO DA UNIDADE CONSUMIDORA"). Achamos esse rótulo, pegamos as linhas
# seguintes até o CEP e paramos se aparecer outro rótulo (ex.: "ENDERECO DE COBRANCA").
# Depois um leitor específico de cada formato separa rua, número, bairro, cidade e UF.

import re
from difflib import SequenceMatcher, get_close_matches

from .config import COMPANIES, DECOY_LABELS, UFS, normalize


# --------------------------------------------------
# CONFIGURAÇÕES
# --------------------------------------------------


TROCAS_DIGITOS = str.maketrans({"O": "0", "I": "1", "L": "1", "S": "5", "B": "8"})

# CEP com a palavra "CEP" na frente (aceita letras parecidas com números)
CEP_COM_ROTULO = re.compile(r"CEP[:\s]*([0-9OILSB]{5})\s*-?\s*([0-9OILSB]{3})\b")

# CEP solto, só com números (usado quando a palavra "CEP" não foi lida)
CEP_SOLTO = re.compile(r"\b(\d{5})\s*-?\s*(\d{3})\b")

# "RUA X, 123" -> rua e número (aceita 123A e S/N)
RUA_E_NUMERO = re.compile(r"^(?P<rua>.+?)\s*,\s*(?P<numero>\d+[A-Z]?|S/?N)\b")

# Erros comuns do OCR numa sigla de estado (ex.: "R)" em vez de "RJ")
TROCAS_UF = str.maketrans({")": "J", "]": "J", "}": "J", "|": "I", "1": "I", "0": "O", "5": "S"})


def find_cep(texto):
    # Procura um CEP no texto e devolve no formato 00000-000 (ou None se não achar).
    texto = normalize(texto)

    achou = CEP_COM_ROTULO.search(texto)
    if achou:
        digitos = (achou.group(1) + achou.group(2)).translate(TROCAS_DIGITOS)
        return f"{digitos[:5]}-{digitos[5:]}"

    achou = CEP_SOLTO.search(texto)
    if achou:
        return f"{achou.group(1)}-{achou.group(2)}"

    return None


def label_score(rotulo, linha):
    # Quanto da linha se parece com o rótulo, de 0 a 1. Tolera erros de OCR:
    # em vez de exigir o rótulo inteiro, medimos o maior pedaço em comum.
    if rotulo in linha:
        return 1.0

    comparador = SequenceMatcher(None, rotulo, linha, autojunk=False)
    pedaco = comparador.find_longest_match(0, len(rotulo), 0, len(linha))

    return pedaco.size / len(rotulo)


def collect_address_lines(linhas, rotulo, max_linhas=6, nota_minima=0.8):
    # Acha o rótulo do endereço certo e junta as linhas seguintes, até o CEP.
    # Devolve (linhas normalizadas, confiança média do OCR), ou ([], 0) se não achar o rótulo.

    # 1. Normalizar o texto e dar uma nota de semelhança com o rótulo em cada linha
    textos = [normalize(linha.text) for linha in linhas]
    notas = [label_score(rotulo, texto) for texto in textos]

    if not notas or max(notas) < nota_minima:
        return [], 0.0

    inicio = notas.index(max(notas))   # a linha mais parecida com o rótulo

    coletadas = []
    confiancas = []

    # 2. Às vezes o endereço vem na mesma linha do rótulo ("ENDERECO DO IMOVEL: RUA X, 10")
    if rotulo in textos[inicio]:
        resto = textos[inicio].split(rotulo, 1)[1].strip(" :-")
        if resto:
            coletadas.append(resto)
            confiancas.append(linhas[inicio].conf)

    # 3. As linhas seguintes valem até aparecer OUTRO rótulo (ex.: endereço de cobrança) ou o CEP
    outros_rotulos = [empresa.anchor for empresa in COMPANIES.values()] + list(DECOY_LABELS)
    outros_rotulos = [outro for outro in outros_rotulos if outro != rotulo]

    for i in range(inicio + 1, min(inicio + 1 + max_linhas, len(textos))):
        e_outro_rotulo = any(label_score(outro, textos[i]) >= nota_minima for outro in outros_rotulos)
        if e_outro_rotulo:
            break

        coletadas.append(textos[i])
        confiancas.append(linhas[i].conf)

        if find_cep(textos[i]):   # o CEP é a última linha do endereço
            break

    media = 0.0
    if confiancas:
        media = sum(confiancas) / len(confiancas)

    return coletadas, media


# --------------------------------------------------
# PEDAÇOS DO ENDEREÇO
# --------------------------------------------------

def split_street_number(texto):
    # "RUA X, 123" -> ("RUA X", "123"). Se não tiver número, devolve ("RUA X", "").
    achou = RUA_E_NUMERO.match(texto)
    if achou:
        return achou.group("rua").strip(), achou.group("numero")
    return texto.strip(), ""


def _clean_uf(texto):
    # Corrige ruído de OCR numa sigla de estado (ex.: "R)" vira "RJ").
    # Devolve "" se não der para chegar numa sigla válida.
    letras = re.sub(r"[^A-Z]", "", texto.upper().translate(TROCAS_UF))

    if letras in UFS:
        return letras

    if len(letras) == 2:
        parecidas = get_close_matches(letras, sorted(UFS), n=1, cutoff=0.5)
        if parecidas:
            return parecidas[0]

    return ""


def _split_city_uf(texto):
    # "RIO DE JANEIRO/RJ" ou "CAMPINAS - SP" -> (cidade, uf)
    achou = re.match(r"^(.*?)\s*[-/]\s*(\S{1,3})\s*$", texto.strip())
    if not achou:
        return texto.strip(), ""

    cidade = achou.group(1).strip(" -")
    uf = _clean_uf(achou.group(2))
    return cidade, uf


def _find_uf(texto):
    # Última sigla de estado válida que aparece depois de "-", "/" ou ","
    candidatas = re.findall(r"(?:-|/|,)\s*([A-Z]{2})\b", texto)
    validas = [sigla for sigla in candidatas if sigla in UFS]

    if validas:
        return validas[-1]
    return ""


def _remove_cep(texto):
    return re.sub(r"CEP[:\s]*[0-9OILSB]{5}\s*-?\s*[0-9OILSB]{3}", "", texto).strip(" -/,")


def _address(linhas, linha_da_rua, bairro, cidade, uf):
    # Monta o dicionário final (o mesmo formato para os três leitores).
    rua, numero = split_street_number(linha_da_rua)
    cep = find_cep(" ".join(linhas)) or ""

    return {
        "logradouro": rua,
        "numero": numero,
        "bairro": bairro,
        "cidade": cidade,
        "uf": uf,
        "cep": cep,
    }


# --------------------------------------------------
# UM LEITOR POR FORMATO DE FATURA
# --------------------------------------------------

def parse_multiline(linhas):
    # Formato da Enel, cada informação numa linha:
    #   RUA X, 123
    #   BAIRRO
    #   CIDADE - UF
    #   CEP 00000-000
    # Usamos a linha do CEP como referência: a cidade é a de cima e o bairro, a de cima dela.
    linha_do_cep = len(linhas) - 1
    for i in range(len(linhas)):
        if find_cep(linhas[i]):
            linha_do_cep = i
            break

    linha_da_cidade = ""
    if linha_do_cep >= 1:
        linha_da_cidade = linhas[linha_do_cep - 1]

    bairro = ""
    if linha_do_cep >= 2:
        bairro = linhas[linha_do_cep - 2]

    # A rua pode ter quebrado em mais de uma linha: juntamos tudo que está antes do bairro
    linha_da_rua = " ".join(linhas[: max(linha_do_cep - 2, 1)])

    cidade, uf = _split_city_uf(linha_da_cidade)
    return _address(linhas, linha_da_rua, bairro, cidade, uf)


def parse_street_bairro(linhas):
    # Formato da Sabesp, duas linhas:
    #   RUA X, 123 - BAIRRO
    #   CEP 00000-000 - CIDADE/UF
    primeira = ""
    if linhas:
        primeira = linhas[0]

    linha_da_rua, _, bairro = primeira.partition(" - ")

    ultima = ""
    if len(linhas) > 1:
        ultima = linhas[-1]

    cidade, uf = _split_city_uf(_remove_cep(ultima))
    return _address(linhas, linha_da_rua, bairro.strip(), cidade, uf)


def parse_inline(linhas):
    # Formato da Claro, duas linhas:
    #   RUA X, 123, COMPLEMENTO
    #   BAIRRO - CIDADE - UF - CEP 00000-000
    ultima = ""
    if len(linhas) > 1:
        ultima = linhas[-1]

    partes = [parte.strip() for parte in _remove_cep(ultima).split(" - ") if parte.strip()]

    bairro = partes[0] if len(partes) > 0 else ""
    cidade = partes[1] if len(partes) > 1 else ""

    if len(partes) > 2:
        uf = _clean_uf(partes[2])
    else:
        uf = _find_uf(ultima)

    linha_da_rua = linhas[0] if linhas else ""
    return _address(linhas, linha_da_rua, bairro, cidade, uf)


# Qual leitor usar em cada formato (o formato de cada empresa está em config.py)
PARSERS = {
    "multiline": parse_multiline,
    "street_bairro": parse_street_bairro,
    "inline": parse_inline,
}


def extract_address(linhas, empresa):
    # Devolve (endereço em campos, linhas brutas, confiança do OCR de 0 a 1).
    # `empresa` é a chave: "enel", "sabesp" ou "claro".
    dados = COMPANIES[empresa]

    linhas_do_endereco, confianca = collect_address_lines(linhas, dados.anchor)
    if not linhas_do_endereco:
        return {}, [], 0.0

    leitor = PARSERS[dados.layout]
    endereco = leitor(linhas_do_endereco)

    return endereco, linhas_do_endereco, round(confianca / 100.0, 3)
