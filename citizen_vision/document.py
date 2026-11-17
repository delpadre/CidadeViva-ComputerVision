# Etapa 1: localizar a folha na foto e corrigir a perspectiva.
#
# Ideia: a conta está sobre uma mesa mais escura. Separamos a folha do fundo,
# achamos os 4 cantos dela e "esticamos" a folha para ficar reta, como num scanner.

import cv2
import numpy as np


# --------------------------------------------------
# CONFIGURAÇÕES
# --------------------------------------------------

# Largura da folha depois de endireitada, em pixels (A4 a uns 150 dpi).
# A altura é calculada para manter a proporção da folha.
LARGURA_SAIDA = 1240

# Para achar a folha, a foto é reduzida até ter no máximo este tamanho no lado maior.
# Foto menor = processamento mais rápido.
LADO_MAXIMO = 1000

# A folha precisa ocupar pelo menos esta parte da foto (0.2 = 20%).
# Se for menor, não consideramos que achamos o documento.
AREA_MINIMA = 0.2


def order_points(pontos):
    # Coloca os 4 cantos sempre na mesma ordem:
    # topo-esquerda, topo-direita, base-direita, base-esquerda.
    pontos = np.array(pontos, dtype="float32").reshape(4, 2)

    soma = pontos.sum(axis=1)            # x + y: o menor é o topo-esquerda, o maior é a base-direita
    diferenca = np.diff(pontos, axis=1).ravel()   # y - x: o menor é o topo-direita, o maior é a base-esquerda

    return np.array(
        [
            pontos[np.argmin(soma)],
            pontos[np.argmin(diferenca)],
            pontos[np.argmax(soma)],
            pontos[np.argmax(diferenca)],
        ],
        dtype="float32",
    )


def find_document_quad(imagem):
    # Devolve os 4 cantos da folha (nas coordenadas da foto original) ou None se não achar.

    # 1. Reduzir a foto
    altura, largura = imagem.shape[:2]
    escala = 1.0
    if max(altura, largura) > LADO_MAXIMO:
        escala = LADO_MAXIMO / max(altura, largura)

    if escala != 1.0:
        pequena = cv2.resize(imagem, None, fx=escala, fy=escala)
    else:
        pequena = imagem

    # 2. Tons de cinza e suavização (tira o ruído da foto)
    cinza = cv2.cvtColor(pequena, cv2.COLOR_BGR2GRAY)
    suave = cv2.GaussianBlur(cinza, (7, 7), 0)

    # 3. Separar folha (clara) e mesa (escura) com o método de Otsu
    _, mascara = cv2.threshold(
        suave,
        0,      # o limiar é escolhido sozinho pelo Otsu
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU,
    )

    # 4. Fechar buracos dentro da folha (o texto deixa pontos escuros na máscara)
    mascara = cv2.morphologyEx(
        mascara,
        cv2.MORPH_CLOSE,
        np.ones((15, 15), np.uint8),
    )

    # 5. Pegar o maior contorno: é a folha
    contornos, _ = cv2.findContours(
        mascara,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    if not contornos:
        return None

    maior = max(contornos, key=cv2.contourArea)
    area_foto = pequena.shape[0] * pequena.shape[1]
    if cv2.contourArea(maior) < AREA_MINIMA * area_foto:
        return None

    # 6. Simplificar o contorno para 4 cantos.
    # Se não der exatamente 4, usamos o retângulo rotacionado que cobre o contorno.
    perimetro = cv2.arcLength(maior, True)
    aproximado = cv2.approxPolyDP(maior, 0.02 * perimetro, True)

    if len(aproximado) == 4:
        cantos = aproximado.reshape(4, 2)
    else:
        cantos = cv2.boxPoints(cv2.minAreaRect(maior))

    # 7. Voltar para o tamanho da foto original
    return order_points(cantos / escala)


def warp_document(imagem, cantos):
    # Endireita a folha: transforma os 4 cantos num retângulo.
    topo_esq, topo_dir, base_dir, base_esq = cantos

    largura = max(np.linalg.norm(topo_dir - topo_esq), np.linalg.norm(base_dir - base_esq))
    altura = max(np.linalg.norm(base_esq - topo_esq), np.linalg.norm(base_dir - topo_dir))

    largura_saida = LARGURA_SAIDA
    altura_saida = int(round(largura_saida * altura / largura))   # mantém a proporção

    destino = np.array(
        [
            [0, 0],
            [largura_saida - 1, 0],
            [largura_saida - 1, altura_saida - 1],
            [0, altura_saida - 1],
        ],
        dtype="float32",
    )

    matriz = cv2.getPerspectiveTransform(cantos, destino)

    return cv2.warpPerspective(
        imagem,
        matriz,
        (largura_saida, altura_saida),   # tamanho do resultado: largura primeiro
        flags=cv2.INTER_CUBIC,           # interpolação suave, melhor para texto
    )


def rectify(imagem):
    # Devolve (imagem endireitada, True se achou a folha).
    cantos = find_document_quad(imagem)

    if cantos is None:
        # Não achou a folha: usa a foto inteira, só ajustando a largura.
        largura = imagem.shape[1]
        escala = LARGURA_SAIDA / largura
        return cv2.resize(imagem, None, fx=escala, fy=escala), False

    return warp_document(imagem, cantos), True
