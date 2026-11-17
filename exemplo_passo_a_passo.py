
import os
import sys

import cv2
import pytesseract

from citizen_vision.classify import classify_company
from citizen_vision.document import rectify
from citizen_vision.extract import extract_address
from citizen_vision.ocr import ocr_lines, pick_lang
from citizen_vision.preprocess import preprocess
from citizen_vision.validate import check_fields


# --------------------------------------------------
# CONFIGURAÇÕES
# --------------------------------------------------

# Foto que será lida. Pode ser trocada passando outro caminho na linha de comando.
CAMINHO_PADRAO = "docs/samples/enel_000.jpg"

# Pasta onde as imagens de cada etapa são salvas para você abrir e conferir.
PASTA_SAIDA = "saida_exemplo"

# Linhas com confiança abaixo disso (em %) são listadas como "baixa confiança".
LIMIAR = 70


# Localizar o Tesseract no Windows (no Linux/Codespaces ele já está no PATH)
possiveis_caminhos = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]

for caminho in possiveis_caminhos:
    if os.path.exists(caminho):
        pytesseract.pytesseract.tesseract_cmd = caminho
        break


# --------------------------------------------------
# 1. CARREGAR A IMAGEM
# --------------------------------------------------

caminho_imagem = sys.argv[1] if len(sys.argv) > 1 else CAMINHO_PADRAO

imagem = cv2.imread(caminho_imagem)

if imagem is None:
    raise FileNotFoundError(f"Imagem não encontrada: {caminho_imagem}")

os.makedirs(PASTA_SAIDA, exist_ok=True)

print("=== 1. IMAGEM CARREGADA ===")
print("Arquivo:", caminho_imagem)
print("Tamanho (altura, largura, canais):", imagem.shape)


# --------------------------------------------------
# 2. ENDIREITAR A FOLHA (perspectiva)
# --------------------------------------------------

folha, achou_documento = rectify(imagem)

cv2.imwrite(f"{PASTA_SAIDA}/1_folha_endireitada.png", folha)

print("\n=== 2. FOLHA ENDIREITADA ===")
print("Achou os cantos da folha:", achou_documento)
print("Novo tamanho:", folha.shape[:2])


# --------------------------------------------------
# 3. PRÉ-PROCESSAMENTO (sombra, inclinação, ruído)
# --------------------------------------------------

preparada = preprocess(folha)

cv2.imwrite(f"{PASTA_SAIDA}/2_pronta_para_ocr.png", preparada["enhanced"])
cv2.imwrite(f"{PASTA_SAIDA}/3_binaria.png", preparada["binary"])

print("\n=== 3. PRÉ-PROCESSAMENTO ===")
print("Inclinação corrigida (graus):", preparada["skew"])


# --------------------------------------------------
# 4. OCR: ler o texto
# --------------------------------------------------

idioma = pick_lang()
linhas = ocr_lines(preparada["enhanced"], lang=idioma)

print("\n=== 4. TEXTO RECONHECIDO ===")
print("Idioma usado:", idioma)

for linha in linhas:
    print(f"{linha.conf:5.1f}%  {linha.text}")

confiancas = [linha.conf for linha in linhas]

if confiancas:
    media = sum(confiancas) / len(confiancas)
    print(f"\nConfiança média: {media:.1f}%")

print(f"\n=== ABAIXO DE {LIMIAR}% DE CONFIANÇA ===")

for linha in linhas:
    if linha.conf < LIMIAR:
        print(f"{linha.conf:5.1f}%  {linha.text}")


# --------------------------------------------------
# 5. DESCOBRIR A EMPRESA
# --------------------------------------------------

empresa, confianca_empresa = classify_company(linhas)

print("\n=== 5. EMPRESA ===")
print("Empresa:", empresa)
print("Confiança:", confianca_empresa)

if empresa is None:
    print("Não reconhecemos a empresa. O cidadão digitaria o endereço.")
    sys.exit()


# --------------------------------------------------
# 6. ACHAR O ENDEREÇO CERTO (entre os vários da fatura)
# --------------------------------------------------

endereco, linhas_do_endereco, confianca_ocr = extract_address(linhas, empresa)

print("\n=== 6. LINHAS DO ENDEREÇO ===")

for linha in linhas_do_endereco:
    print(" ", linha)

print("\nEndereço separado em campos:")

for campo, valor in endereco.items():
    print(f"  {campo:12} {valor}")


# --------------------------------------------------
# 7. VALIDAR
# --------------------------------------------------

avisos, campos_para_conferir = check_fields(endereco)

print("\n=== 7. VALIDAÇÃO ===")

if avisos:
    print("Avisos:", avisos)
    print("O cidadão deve conferir:", campos_para_conferir)
else:
    print("Nenhum aviso. O cidadão ainda confirma o endereço antes de salvar.")

print(f"\nImagens de cada etapa salvas em: {PASTA_SAIDA}/")
