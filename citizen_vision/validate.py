# Etapa 6: validação do endereço extraído.
#
# Um campo é "duvidoso" quando está vazio OU quando tem algo que não faz sentido
# (por exemplo, um pedaço de outra parte da fatura que o OCR leu por engano).
# A página de confirmação destaca esses campos para o cidadão conferir.

import json
import re
import urllib.request

from .config import UFS


# Campos que um endereço completo precisa ter (o complemento é opcional)
REQUIRED = ("logradouro", "numero", "bairro", "cidade", "uf", "cep")

# Cidade: só letras, espaço, ponto, apóstrofo e hífen (sem dígitos nem outros símbolos)
PADRAO_CIDADE = re.compile(r"^[A-Z][A-Z .'\-]*$")

# Bairro: igual, mas pode ter números (ex.: "JARDIM 2")
PADRAO_BAIRRO = re.compile(r"^[A-Z0-9][A-Z0-9 .'\-]*$")


def check_fields(endereco):
    # Devolve (avisos, campos duvidosos).
    problemas = []   # lista de (campo, mensagem)

    # 1. Campos que faltam
    for campo in REQUIRED:
        if not endereco.get(campo):
            problemas.append((campo, f"campo ausente: {campo}"))

    # 2. CEP no formato 00000-000
    if endereco.get("cep") and not re.fullmatch(r"\d{5}-\d{3}", endereco["cep"]):
        problemas.append(("cep", "CEP em formato inválido"))

    # 3. UF que existe
    if endereco.get("uf") and endereco["uf"] not in UFS:
        problemas.append(("uf", "UF inválida"))

    # 4. Cidade e bairro sem conteúdo estranho
    cidade = endereco.get("cidade", "")
    bairro = endereco.get("bairro", "")

    if cidade and not PADRAO_CIDADE.match(cidade):
        problemas.append(("cidade", "cidade com conteúdo suspeito"))

    if bairro and (not PADRAO_BAIRRO.match(bairro) or re.search(r"\bCEP\b", bairro)):
        problemas.append(("bairro", "bairro com conteúdo suspeito"))

    # 5. Separar as mensagens dos nomes de campo (sem repetir campo, na mesma ordem)
    avisos = [mensagem for _, mensagem in problemas]
    campos = list(dict.fromkeys(campo for campo, _ in problemas))

    return avisos, campos


def validate_address(endereco):
    # Só os avisos (sem a lista de campos).
    return check_fields(endereco)[0]


def check_viacep(cep, timeout=3.0):
    # Confere o CEP no ViaCEP (serviço público dos Correios). Opcional: precisa de internet.
    # Devolve o JSON do ViaCEP, ou None se o CEP não existe ou se não houve resposta.
    try:
        url = f"https://viacep.com.br/ws/{cep.replace('-', '')}/json/"
        with urllib.request.urlopen(url, timeout=timeout) as resposta:
            dados = json.load(resposta)

        if dados.get("erro"):
            return None
        return dados
    except Exception:
        return None
