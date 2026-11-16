# CidadeViva Vision — Extração Automática de Endereços

Componente de **Visão Computacional** do MVP **CidadeViva** (nome provisório; plataforma de zeladoria urbana colaborativa) (Global Solution 2026.2 · Applied Computer Vision).
Recebe a **foto de uma fatura**, identifica a empresa, retifica a perspectiva, aplica OCR e devolve o
**endereço correto** (distinguindo-o de endereços de cobrança e sede) para pré-preencher o cadastro.

## Ficha técnica (parte Visão)
| Item | Valor |
|---|---|
| Empresas suportadas | Enel (energia), Sabesp (água), Claro (telecom) — layouts sintéticos |
| Técnicas | Otsu + contornos + homografia, remoção de sombra, denoise NLM, deskew por projeção, Tesseract OCR |
| Distinção de endereço | Âncora de rótulo por empresa (match aproximado) + parser por layout |
| Validação | formato de CEP, UF, campos obrigatórios, ViaCEP opcional |
| Humano no circuito | o MVP sempre mostra o endereço editável; `warnings`/`needs_review` destacam dúvidas |
| LGPD | imagem processada em memória e descartada; dados de teste 100% fictícios |

## Dados de teste
A pasta `dataset/` traz as 90 faturas sintéticas usadas na avaliação (30 por empresa): `<id>.jpg` (foto simulada) + `<id>.json` (gabarito). Dados 100% fictícios; reproduzíveis com `python -m synthetic.generate --n 30 --out dataset --seed 99`.

## Pipeline
`foto → localizar folha + perspectiva → pré-processamento → OCR por linhas → classificar empresa → achar rótulo do endereço correto → parse → validação → JSON`

## Página de confirmação (demo)
`web/index.html` é a tela de cadastro: o cidadão tira a foto da conta, o endereço vem **pré-preenchido e editável**, os campos duvidosos
ficam destacados, e ele confirma. Mobile-first, com rótulos, foco por teclado, linguagem simples, redução da foto no aparelho e opção de
digitar quando a leitura falha. Para integrar ao MVP: ajuste `CONFIRM_URL` (endpoint que salva) ou escute o evento `endereco-confirmado`.

```bash
python demo_server.py        # sem dependências extras  ->  http://localhost:8000
# ou, com FastAPI:  uvicorn api:app --reload
```

## Como rodar
```bash
sudo apt install tesseract-ocr tesseract-ocr-por     # ou brew install tesseract tesseract-lang
pip install -r requirements.txt

python -m synthetic.generate --n 30 --out dataset --seed 99   # gera faturas + fotos + gabarito
python evaluate.py --data dataset --report docs/metrics.json  # métricas
python -m unittest discover -s tests -v                              # testes
uvicorn api:app --reload                                             # API para o MVP
```
Uso em Python: `from citizen_vision import process_image; process_image("foto.jpg").to_dict()`

## Integração com o MVP
`POST /extract-address[?lookup_ibge=true]` (multipart, campo `file`) →
```json
{"company": "enel",
 "address": {"logradouro": "...", "numero": "...", "bairro": "...", "cidade": "...", "uf": "SP", "cep": "00000-000"},
 "municipio": {"municipio": "CAMPINAS", "uf": "SP", "ibge": null, "fonte": "fatura", "confere_cep": null},
 "warnings": [], "fields_to_check": [], "needs_review": true, "ocr_confidence": 0.93}
```
`fields_to_check` lista campos **ausentes ou implausíveis** (ex.: texto de outra parte da fatura lido por engano); a tela os destaca.
`municipio` (nome/UF, e código IBGE quando `lookup_ibge=true`) serve para rotear a solicitação à prefeitura/concessionária certa.
O endereço da fatura é a **residência** do cidadão; o local do problema reportado vem de GPS/mapa, não da fatura.

## Resultados (90 faturas sintéticas, semente inédita 99, 30% "difíceis")
| Métrica | Resultado |
|---|---|
| Empresa identificada | 100% |
| Endereço 100% correto | 98,9% (89/90) |
| Falhas silenciosas (errou sem avisar) | 0 |
| Alarmes falsos (acertou, mas pediu conferência) | 0 |
| Com a foto reduzida a 2000 px (como a página envia) | 97,8% (88/90) |
| CER médio | 0,6% |
| Tempo médio | ~2 s/foto (CPU) |

## Limitações
- Resultados em dados **sintéticos**; fotos reais (amassados, reflexo, baixa resolução) tendem a ter acerto menor.
- Layouts são templates fixos; um layout novo exige adicionar âncora e parser em `config.py`/`extract.py`.
- OCR pode inserir/trocar dígitos (ex.: CEP com dígito extra): o pipeline sinaliza, não "adivinha".
- Saída em MAIÚSCULAS sem acento (padrão Correios).
- Documentos escuros ou com fundo claro semelhante ao papel podem falhar na detecção das bordas (há fallback para a imagem inteira).

> 📘 **Vai integrar com o MVP?** Leia o [guia técnico e de integração](docs/INTEGRACAO.md): contrato da API, exemplos de código, banco, CORS, publicação e limitações.
