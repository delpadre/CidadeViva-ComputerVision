
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
    try:
        return extract_from_bytes(file.file.read(), lookup_ibge=lookup_ibge)
    except ServiceError as e:
        raise HTTPException(e.status, e.message)


app.mount("/", StaticFiles(directory=Path(__file__).parent / "web", html=True), name="web")
