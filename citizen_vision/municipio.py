# Município do cidadão, a partir do endereço da fatura.
# O MVP usa isso para saber a qual prefeitura o cidadão pertence.

from .config import normalize
from .validate import check_viacep


def resolve_municipio(endereco, online=False, lookup=check_viacep):
    # Devolve um dicionário com:
    #   municipio   -> nome da cidade
    #   uf          -> sigla do estado
    #   ibge        -> código IBGE da cidade (só vem no modo online)
    #   fonte       -> "fatura" (lido da conta) ou "viacep" (conferido no ViaCEP)
    #   confere_cep -> False se o CEP aponta para outra cidade que a da fatura; None se não conferimos
    #
    # Offline (padrão): usa só a cidade e a UF lidas da fatura.
    # Online: confere o CEP no ViaCEP (precisa de internet) e obtém o código IBGE.
    resultado = {
        "municipio": endereco.get("cidade", ""),
        "uf": endereco.get("uf", ""),
        "ibge": None,
        "fonte": "fatura",
        "confere_cep": None,
    }

    cep = endereco.get("cep", "")
    if not online or not cep:
        return resultado

    dados = lookup(cep)
    if not dados:   # ViaCEP não respondeu ou não achou o CEP: ficamos com o que veio da fatura
        return resultado

    mesma_cidade = normalize(dados.get("localidade", "")) == normalize(endereco.get("cidade", ""))
    mesmo_estado = dados.get("uf") == endereco.get("uf")

    resultado["municipio"] = normalize(dados.get("localidade", ""))
    resultado["uf"] = dados.get("uf", "")
    resultado["ibge"] = dados.get("ibge")
    resultado["fonte"] = "viacep"
    resultado["confere_cep"] = mesma_cidade and mesmo_estado

    return resultado
