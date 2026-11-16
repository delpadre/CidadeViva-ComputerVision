"""API de integração com o MVP CidadeViva. Rodar: uvicorn api:app --reload

POST /extract-address[?lookup_ibge=true]  (multipart, campo 'file')
GET  /          -> página de confirmação de endereço (web/index.html)
Privacidade (LGPD): a imagem é processada em memória e descartada; nada é gravado nem logado.
"""
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles

from citizen_vision.service import ServiceError, extract_from_bytes

app = FastAPI(title="CidadeViva Vision - Extração de Endereço", version="1.1")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/extract-address")
def extract_address(file: UploadFile = File(...), lookup_ibge: bool = False):
    # função síncrona de propósito: o OCR é CPU-bound e o FastAPI a executa em thread separada
    try:
        return extract_from_bytes(file.file.read(), lookup_ibge=lookup_ibge)
    except ServiceError as e:
        raise HTTPException(e.status, e.message)


# Página de confirmação (deve ser montada por último para não sobrepor as rotas acima)
app.mount("/", StaticFiles(directory=Path(__file__).parent / "web", html=True), name="web")
