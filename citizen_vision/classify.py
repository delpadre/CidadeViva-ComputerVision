# Etapa 4: identificar qual empresa emitiu o documento (Enel, Sabesp ou Claro).
#
# Ideia: cada empresa tem palavras que só aparecem nas contas dela.
# Contamos quantas dessas palavras aparecem no texto lido pelo OCR.

from difflib import get_close_matches

from .config import COMPANIES, normalize


def _kw_score(palavra, texto, palavras_do_texto):
    if palavra in texto:
        return 1.0

    palavra_simples = " " not in palavra and len(palavra) >= 4
    if palavra_simples and get_close_matches(palavra, palavras_do_texto, n=1, cutoff=0.85):
        return 0.8

    return 0.0


def classify_company(linhas):
    texto = normalize(" ".join(linha.text for linha in linhas))
    palavras_do_texto = texto.split()

    pontuacoes = {}
    for chave, empresa in COMPANIES.items():
        pontos = 0.0
        for palavra in empresa.keywords:
            pontos += _kw_score(palavra, texto, palavras_do_texto)
        pontuacoes[chave] = pontos

    melhor = max(pontuacoes, key=pontuacoes.get)
    total = sum(pontuacoes.values())

    if pontuacoes[melhor] < 1.0:
        return None, 0.0

    return melhor, round(pontuacoes[melhor] / total, 3)
