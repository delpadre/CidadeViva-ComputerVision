# Etapa 2: pré-processamento para o OCR.
#
# Ideia: deixar o texto preto num fundo uniforme e claro, sem sombra e sem inclinação.

import cv2
import numpy as np


# --------------------------------------------------
# CONFIGURAÇÕES
# --------------------------------------------------

# Inclinação máxima que testamos (em graus, para os dois lados) e o passo entre os testes.
# Passo menor = mais preciso, porém mais lento.
INCLINACAO_MAXIMA = 6.0
PASSO = 0.5

# Força da limpeza de ruído (fastNlMeansDenoising).
# Valor maior = mais limpeza, mas pode borrar letras pequenas.
FORCA_DENOISE = 7


def remove_shadows(cinza):
    # Tira sombras e luz irregular.
    # Estimamos o fundo (a folha sem o texto) e comparamos com a imagem:
    # o que é igual ao fundo vira branco, o texto continua escuro.
    kernel = np.ones((7, 7), np.uint8)
    sem_texto = cv2.dilate(cinza, kernel)      # a dilatação apaga o texto fino (escuro)
    fundo = cv2.medianBlur(sem_texto, 21)      # suaviza para ficar só a variação da luz

    diferenca = 255 - cv2.absdiff(cinza, fundo)

    return cv2.normalize(diferenca, None, 0, 255, cv2.NORM_MINMAX)


def estimate_skew(binaria_invertida, limit=INCLINACAO_MAXIMA, step=PASSO):
    # Descobre quantos graus o texto está inclinado.
    # Giramos a imagem em vários ângulos e somamos os pixels de cada linha.
    # Quando o texto está reto, as linhas de texto ficam bem separadas
    # e a variação entre as somas é a maior.
    pequena = cv2.resize(binaria_invertida, None, fx=0.4, fy=0.4, interpolation=cv2.INTER_AREA)
    altura, largura = pequena.shape

    melhor_angulo = 0.0
    melhor_pontuacao = -1.0

    for angulo in np.arange(-limit, limit + step, step):
        matriz = cv2.getRotationMatrix2D((largura / 2, altura / 2), angulo, 1.0)
        girada = cv2.warpAffine(pequena, matriz, (largura, altura), flags=cv2.INTER_NEAREST)

        soma_das_linhas = girada.sum(axis=1)
        pontuacao = float(np.var(soma_das_linhas))

        if pontuacao > melhor_pontuacao:
            melhor_angulo = float(angulo)
            melhor_pontuacao = pontuacao

    return melhor_angulo


def rotate(imagem, angulo, border=255):
    # Gira a imagem. Se o ângulo for muito pequeno, não vale a pena girar.
    if abs(angulo) < 0.1:
        return imagem

    altura, largura = imagem.shape[:2]
    matriz = cv2.getRotationMatrix2D((largura / 2, altura / 2), angulo, 1.0)

    return cv2.warpAffine(
        imagem,
        matriz,
        (largura, altura),
        flags=cv2.INTER_CUBIC,
        borderValue=border,   # os cantos que ficam vazios são preenchidos de branco
    )


def preprocess(imagem):
    # Recebe a folha colorida e devolve um dicionário com:
    #   gray     -> a folha em tons de cinza
    #   enhanced -> a imagem limpa, que vai para o OCR
    #   binary   -> versão preto e branco (usada só para depuração)
    #   skew     -> inclinação encontrada, em graus

    # 1. Tons de cinza
    cinza = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)

    # 2. Remover sombras
    sem_sombra = remove_shadows(cinza)

    # 3. Descobrir a inclinação (precisa do texto em branco sobre preto, por isso INV)
    _, binaria_invertida = cv2.threshold(
        sem_sombra,
        0,
        255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU,
    )
    inclinacao = estimate_skew(binaria_invertida)

    # 4. Endireitar o texto
    sem_sombra = rotate(sem_sombra, inclinacao)

    # 5. Limpar o ruído
    limpa = cv2.fastNlMeansDenoising(
        sem_sombra,
        None,
        h=FORCA_DENOISE,       # força da limpeza
        templateWindowSize=7,  # tamanho do pedaço comparado
        searchWindowSize=21,   # região onde procura pedaços parecidos
    )

    # 6. Versão preto e branco (só para conferir no modo de depuração)
    binaria = cv2.adaptiveThreshold(
        limpa,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,   # tamanho da vizinhança
        15,   # constante subtraída
    )

    return {"gray": cinza, "enhanced": limpa, "binary": binaria, "skew": inclinacao}
