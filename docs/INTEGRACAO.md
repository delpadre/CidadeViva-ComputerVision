# Guia técnico e de integração — componente de Visão (ZeloCidade)

Para quem vai construir o **MVP** e precisa encaixar a leitura automática de endereço a partir de fotos de faturas.
Tudo aqui foi verificado contra o código deste repositório; o que **não** foi testado está marcado com ⚠️.

---

## 1. Resumo em 30 segundos

- O componente recebe **uma foto de fatura** (luz, água ou telefone) e devolve **o endereço do imóvel**, separado em campos, mais avisos sobre o que está duvidoso.
- Ele é um **serviço HTTP independente**. O MVP só precisa chamar **um endpoint**: `POST /extract-address`.
- O MVP deve **mostrar o resultado ao cidadão para confirmar ou corrigir** e só então **salvar o endereço**. O serviço **não grava nada**.
- No ZeloCidade, o endereço serve para saber **de qual município/bairro** o cidadão é (rotear a solicitação para a prefeitura certa e alimentar indicadores por bairro). O **local do problema reportado** vem de GPS/mapa, **não** da fatura.

```
 Celular / navegador                Serviço de Visão (este repo)              Backend do MVP
┌───────────────────┐  foto   ┌─────────────────────────────────────┐
│ Tela de cadastro  │ ──────► │ POST /extract-address               │
│ (do MVP)          │ ◄────── │  retifica → pré-proc. → OCR →       │
│                   │  JSON   │  empresa → endereço → validação     │
└─────────┬─────────┘         └─────────────────────────────────────┘
          │ cidadão confere/corrige e confirma
          ▼
┌───────────────────┐  POST JSON (endereço confirmado)   ┌──────────────┐
│ Front do MVP      │ ─────────────────────────────────► │ Backend + BD │
└───────────────────┘                                    └──────────────┘
```

---

## 2. Como o pipeline funciona (por dentro)

| # | Etapa | Arquivo | O que faz |
|---|---|---|---|
| 1 | Retificar | `citizen_vision/document.py` | Acha os 4 cantos da folha (Otsu + maior contorno) e corrige a perspectiva (homografia) para 1240 px de largura. Se não achar bordas, usa a imagem inteira e avisa. |
| 2 | Pré-processar | `citizen_vision/preprocess.py` | Remove sombra, corrige inclinação residual, reduz ruído. |
| 3 | OCR | `citizen_vision/ocr.py` | Tesseract; devolve linhas com texto, confiança e posição. Usa `por+eng` se o idioma português estiver instalado, senão `eng`. |
| 4 | Identificar a empresa | `citizen_vision/classify.py` | Pontua palavras-chave de cada empresa (tolera erro de OCR). |
| 5 | Achar o endereço certo | `citizen_vision/extract.py` | Procura o **rótulo** do endereço correto da empresa (ex.: "ENDERECO DE ENTREGA DA FATURA") e coleta as linhas seguintes até o CEP, parando se aparecer o rótulo de outro bloco. Os endereços de **cobrança** e **sede** são ignorados de propósito. |
| 6 | Estruturar | `citizen_vision/extract.py` | Um *parser* por layout transforma as linhas em logradouro, número, bairro, cidade, UF, CEP. Corrige confusões de OCR (O↔0, `)`→J em UF). |
| 7 | Validar | `citizen_vision/validate.py` | CEP no formato `00000-000`, UF existente, campos obrigatórios, e campos **suspeitos** (ex.: cidade com dígitos, bairro contendo "CEP"). |
| 8 | Município | `citizen_vision/municipio.py` | Município/UF a partir da fatura; opcionalmente confere o CEP no ViaCEP e traz o código IBGE. |

Camadas de código:

- `citizen_vision/pipeline.py` → `process_image(imagem)` (caminho ou array BGR) devolve um `ExtractionResult`.
- `citizen_vision/service.py` → `extract_from_bytes(bytes, lookup_ibge)` valida tamanho/formato, roda o pipeline e acrescenta o município. **É a função usada pelos dois servidores.**
- `demo_server.py` (só biblioteca padrão) e `api.py` (FastAPI) expõem o mesmo contrato HTTP.
- `web/index.html` é uma tela pronta de confirmação (referência de UX e de uso da API).

Empresas atendidas hoje: **Enel (energia), Sabesp (água), Claro (telecom)**, em layouts **sintéticos** (imitações simplificadas, dados fictícios).

---

## 3. Contrato da API

### `POST /extract-address`

- **Corpo:** `multipart/form-data`, campo **`file`** com a imagem (JPEG/PNG). Máximo **8 MB**.
- **Query opcional:** `?lookup_ibge=true` → confere o CEP no ViaCEP e preenche o código IBGE (o **servidor** precisa de internet; se o ViaCEP falhar, cai para a cidade da fatura, sem erro).
- **Tempo típico:** cerca de 2 s por foto (CPU), medido neste repositório.

Exemplo de resposta real (documento sintético `claro_000.jpg`):

```json
{
  "company": "claro",
  "company_confidence": 1.0,
  "document_found": true,
  "address": {
    "logradouro": "RUA QUINZE DE NOVEMBRO",
    "numero": "442",
    "bairro": "TATUAPE",
    "cidade": "PORTO ALEGRE",
    "uf": "RS",
    "cep": "94627-341"
  },
  "address_lines": [
    "RUA QUINZE DE NOVEMBRO, 442, CASA 2",
    "TATUAPE - PORTO ALEGRE - RS - CEP 94627-341"
  ],
  "ocr_confidence": 0.94,
  "warnings": [],
  "fields_to_check": [],
  "needs_review": true,
  "timings_ms": { "retificacao": 265, "preprocessamento": 909, "ocr": 769, "total": 1945 },
  "municipio": { "municipio": "PORTO ALEGRE", "uf": "RS", "ibge": null, "fonte": "fatura", "confere_cep": null }
}
```

### Campos da resposta

| Campo | Tipo | Significado |
|---|---|---|
| `company` | `"enel"`, `"sabesp"`, `"claro"` ou `null` | Empresa reconhecida. `null` = não reconheceu: **abrir o formulário vazio**. |
| `company_confidence` | 0–1 | Confiança da identificação da empresa. |
| `document_found` | bool | `false` = não achou as bordas da folha (usou a imagem inteira). |
| `address` | objeto | `logradouro`, `numero`, `bairro`, `cidade`, `uf`, `cep`. **Texto em MAIÚSCULAS e sem acento** (padrão Correios). Campo não lido vem como `""`. Pode vir `{}`. |
| `address_lines` | lista | Linhas brutas lidas do bloco de endereço (útil para depuração). |
| `ocr_confidence` | 0–1 | Confiança média do OCR nessas linhas. |
| `warnings` | lista de textos | Problemas detectados (campo ausente, CEP inválido, "baixa confiança do OCR", etc.). |
| `fields_to_check` | lista | **Campos a destacar na tela**: ausentes **ou** implausíveis. Nomes: `logradouro`, `numero`, `bairro`, `cidade`, `uf`, `cep`. |
| `needs_review` | bool | **Sempre `true`**, por decisão de projeto (humano no circuito). |
| `timings_ms` | objeto | Tempo por etapa. |
| `municipio` | objeto ou `null` | `municipio`, `uf`, `ibge` (só com `lookup_ibge=true`), `fonte` (`"fatura"` ou `"viacep"`), `confere_cep` (`false` = o CEP aponta para outra cidade/UF). É `null` quando a cidade lida é duvidosa, para **não** mostrar município falso. |

### Erros

Sempre JSON `{"detail": "mensagem"}`:

| HTTP | Quando | O que o front deve fazer |
|---|---|---|
| 400 | Sem arquivo, ou arquivo que não é imagem | Pedir outra foto / oferecer digitação |
| 413 | Imagem maior que 8 MB | Reduzir a foto antes de enviar |
| 503 | Tesseract não instalado no servidor | Erro de infraestrutura; oferecer digitação |
| 500 | Falha inesperada ao processar | Oferecer digitação |
| (sem resposta / `Failed to fetch`) | Servidor fora do ar ou rota errada | Oferecer digitação |

> Regra de ouro: **o cadastro nunca pode ficar bloqueado**. Em qualquer erro, ofereça digitar o endereço à mão.

### `GET /health` → `{"status": "ok"}` (para monitoramento).

---

## 4. Como integrar no MVP

### 4.1 O fluxo que o MVP deve implementar

1. Cidadão toca em "Tirar foto da conta".
2. Front envia a foto para `POST /extract-address`.
3. Front mostra os campos **pré-preenchidos e editáveis**; destaca os de `fields_to_check` (texto "Falta" se vazio, "Confira" se preenchido).
4. Se `company` for `null` ou der erro → formulário **vazio** para digitar.
5. Cidadão confere/corrige e confirma. **O front valida de novo** (CEP, UF, obrigatórios).
6. Front envia o **endereço confirmado** ao backend do MVP, que salva no banco.
7. O MVP usa o endereço: município/bairro-base do usuário (roteamento e indicadores).

### 4.2 Chamada pelo front (JavaScript puro)

```js
async function lerEndereco(arquivoFoto) {
  const fd = new FormData();
  fd.append("file", arquivoFoto, "conta.jpg");           // o campo TEM que se chamar "file"
  const resp = await fetch("https://SEU-SERVICO/extract-address", { method: "POST", body: fd });
  if (!resp.ok) {
    const erro = await resp.json().catch(() => ({}));
    throw new Error(erro.detail || `erro ${resp.status}`);
  }
  return resp.json();   // veja os campos na seção 3
}
```

Dicas que `web/index.html` já aplica e valem copiar:
- **Reduzir a foto no aparelho** (lado maior ≤ 2000 px, JPEG ~90%) antes de enviar: conexão ruim e limite de 8 MB. (Medido: o acerto com foto reduzida a 2000 px ficou muito próximo ao da original.)
- **Timeout** (a página usa 60 s) e mensagem humana quando o fetch falha.
- Campo de arquivo com `accept="image/*"` (no celular abre a câmera ou a galeria).

### 4.3 Chamada pelo backend (Python)

```python
import requests
with open("conta.jpg", "rb") as f:
    r = requests.post("https://SEU-SERVICO/extract-address", files={"file": f}, timeout=60)
r.raise_for_status()
dados = r.json()
```

### 4.4 Usar o código como biblioteca (se o backend do MVP for Python)

Dispensa o HTTP. Copie as pastas `citizen_vision/` e instale as dependências:

```python
from citizen_vision.service import extract_from_bytes, ServiceError
try:
    dados = extract_from_bytes(bytes_da_imagem, lookup_ibge=False)
except ServiceError as e:
    ...  # e.status (400/413/503/500) e e.message
```

### 4.5 Salvar o endereço confirmado

O serviço de Visão **não tem banco**. O MVP precisa de um endpoint próprio que receba o endereço confirmado. Sugestão de payload (é o mesmo que `web/index.html` monta):

```json
{
  "endereco": { "cep": "94627-341", "uf": "RS", "logradouro": "RUA QUINZE DE NOVEMBRO",
                "numero": "442", "complemento": "CASA 2", "bairro": "TATUAPE", "cidade": "PORTO ALEGRE" },
  "origem": "foto",
  "empresa": "claro",
  "municipio": { "municipio": "PORTO ALEGRE", "uf": "RS", "ibge": null, "fonte": "fatura", "confere_cep": null },
  "editado_pelo_usuario": false,
  "confirmado_em": "2026-11-17T15:00:00.000Z"
}
```

Sugestão de tabela (adapte ao banco do MVP):

```sql
CREATE TABLE endereco_usuario (
  usuario_id   TEXT PRIMARY KEY,
  cep          TEXT NOT NULL,
  uf           TEXT NOT NULL,
  logradouro   TEXT NOT NULL,
  numero       TEXT NOT NULL,
  complemento  TEXT,
  bairro       TEXT NOT NULL,
  cidade       TEXT NOT NULL,
  ibge         TEXT,
  origem       TEXT NOT NULL,          -- 'foto' | 'manual'
  confirmado_em TIMESTAMP NOT NULL
);
```

**Não salve a foto.** Salve só o endereço confirmado (LGPD: minimização).

### 4.6 Se a tela do MVP reaproveitar `web/index.html`

Há dois pontos de configuração no topo do `<script>`:

```js
const API_URL = "/extract-address";  // URL do serviço de leitura
const CONFIRM_URL = null;            // URL do endpoint do MVP que SALVA (POST JSON). null = só demonstração
const LOOKUP_IBGE = false;           // true = conferir CEP no ViaCEP / obter IBGE
```

Ao confirmar, a página também dispara um evento no `document`:
`document.addEventListener("endereco-confirmado", e => console.log(e.detail))` (o `detail` é o payload da seção 4.5). Ele **só funciona se a página estiver no mesmo documento** do MVP; dentro de um `<iframe>` de outro domínio não atravessa — use `CONFIRM_URL`.

### 4.7 Usar o município no MVP

- **Roteamento:** `municipio.municipio` + `municipio.uf` (ou `ibge`) decidem para qual prefeitura/concessionária vai a solicitação. Prefira o `ibge` quando existir (chave estável); o nome vem em MAIÚSCULAS sem acento e pode ter variações.
- **Bairro-base:** `address.bairro`, para indicadores por bairro (pipeline de Dados).
- **Local do problema:** vem de GPS/pino no mapa. **Não** use o endereço da fatura para isso (é a residência).
- Se `municipio.confere_cep === false`, mostre um aviso: o CEP e a cidade da fatura não combinam.

---

## 5. Rodar e publicar

### 5.1 Rodar localmente

Requer **Tesseract** instalado (programa à parte, não é pacote do pip) e, de preferência, o idioma **português**.

```bash
pip install -r requirements.txt
python demo_server.py            # http://localhost:8000  (sem dependências extras; mesma API)
# ou, com FastAPI:
uvicorn api:app --host 0.0.0.0 --port 8000
```

- Ubuntu/Debian/Codespaces: `sudo apt install -y tesseract-ocr tesseract-ocr-por`
- Windows: `winget install --id UB-Mannheim.TesseractOCR` (depois abra um terminal novo; se `tesseract --version` falhar, ajuste o PATH ou defina `pytesseract.pytesseract.tesseract_cmd`).

### 5.2 CORS ⚠️ (provável bloqueio se o front estiver em outro endereço)

Se o front do MVP roda em um domínio/porta **diferente** do serviço de Visão, o navegador bloqueia a chamada (CORS). **Nem `demo_server.py` nem `api.py` enviam cabeçalhos CORS hoje.** Opções:

1. **Servir front e serviço no mesmo endereço** (a página `web/` já faz isso), ou usar um *proxy reverso*.
2. **Habilitar CORS no FastAPI** (⚠️ trecho não testado, FastAPI não estava instalado onde este guia foi escrito):

```python
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=["https://URL-DO-FRONT-DO-MVP"],
                   allow_methods=["POST", "GET"], allow_headers=["*"])
```

Evite `allow_origins=["*"]` em produção.

### 5.3 Publicar na Azure (disciplina de DevOps) ⚠️

O serviço depende do programa **Tesseract no sistema operacional**. A imagem padrão do Azure App Service (Python) normalmente **não** o inclui. Caminhos possíveis, **nenhum testado aqui**:

- **Contêiner Docker customizado** (o mais seguro). Esboço de `Dockerfile`:
  ```dockerfile
  FROM python:3.12-slim
  RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-por \
      && rm -rf /var/lib/apt/lists/*
  WORKDIR /app
  COPY requirements.txt . 
  RUN pip install --no-cache-dir -r requirements.txt
  COPY . .
  CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
  ```
- **Script de inicialização** do App Service que instala o pacote antes de subir (mais frágil).

Combine com quem faz o DevOps. Cuide de: HTTPS, limite de 8 MB, **nada de log com conteúdo de imagem**, e que o plano tenha CPU suficiente (o OCR leva ~2 s por foto).

---

## 6. Segurança, LGPD e IA responsável

- A imagem é lida **em memória e descartada**: nada é gravado em disco nem logado (o `demo_server.py` desativa o log de requisições).
- Só o **endereço confirmado** deve ser persistido, para a finalidade de cadastro. Diga isso ao usuário na tela.
- **Humano no circuito:** `needs_review` é sempre `true`; nenhum endereço deve ser salvo sem o cidadão ver e aceitar.
- **Transparência do modelo:** a decisão não vem de modelo opaco: é OCR + regras explícitas (rótulos por empresa, *parsers*, validações), o que facilita explicar e auditar.
- Dados de teste do repositório são **100% sintéticos**.

---

## 7. Adicionar uma nova empresa

1. Em `citizen_vision/config.py`, acrescente uma entrada em `COMPANIES` com: `keywords` (palavras que identificam a empresa), `anchor` (o rótulo do endereço **correto**, já sem acento e em maiúsculas) e `layout`.
2. Se o formato do endereço for diferente, escreva um *parser* novo em `citizen_vision/extract.py` e registre-o em `PARSERS`.
3. Se o rótulo de cobrança/sede dessa empresa for diferente, inclua-o em `DECOY_LABELS` (impede que o texto "vaze" para o endereço certo).
4. Em `synthetic/generate.py`, crie um *template* sintético correspondente (com gabarito).
5. Rode `python -m synthetic.generate ...` e `python evaluate.py ...` para medir, e os testes.

---

## 8. Testes e métricas

```bash
python -m unittest discover -s tests -v          # 23 testes (a parte da página usa Playwright e é pulada se ele não existir)
python evaluate.py --data dataset --report docs/metrics.json
```

O avaliador compara cada foto com o gabarito (`dataset/<id>.json`) e mede: acerto da empresa, acerto por campo, endereço 100% correto, CER, **falhas silenciosas** (erro sem aviso) e **alarmes falsos**.

Medições feitas neste repositório (mesmas 90 faturas sintéticas de `dataset/`):

| Ambiente | Idiomas do Tesseract | Endereço 100% correto | Falhas silenciosas |
|---|---|---|---|
| A (usado no PDF) | só inglês | 98,9% (89/90) | 0 |
| B | português + inglês (Tesseract 5.3.4, OpenCV 5.0.0) | 100% (90/90) | 0 |

⚠️ **Os números variam com o ambiente.** O resultado do OCR depende da versão do Tesseract e das bibliotecas (OpenCV, Pillow) e de ter ou não o idioma português. Por isso `requirements.txt` deve ter as versões fixadas, e os números do PDF devem ser os medidos **no ambiente final**. Rode o avaliador no ambiente onde o projeto será entregue e confira se batem com o PDF.

---

## 9. Limitações conhecidas

- Resultados medidos em documentos **sintéticos** com fotos **simuladas**; fotos reais devem ter acerto menor.
- Layouts fixos por empresa; mudança de layout ou nova empresa exige novo *template*.
- **Complemento** (apto, bloco): o serviço **não** o devolve, mesmo se estiver na fatura (ex.: "CASA 2" no exemplo acima). O front tem o campo, e o cidadão preenche.
- A empresa é identificada por **texto** (não por logotipo).
- Saída em maiúsculas sem acento.
- Enel, Sabesp e Claro **não atendem todos os municípios**; em cidades pequenas, água e energia costumam vir de autarquias ou concessionárias locais.
- Uma foto muito escura ou com fundo claro parecido com o papel pode falhar na detecção das bordas (há *fallback*, com aviso).
- O OCR pode trocar, omitir ou inserir dígitos (ex.: CEP com dígito extra). O serviço **sinaliza** em vez de adivinhar.

---

## 10. Problemas comuns

| Sintoma | Causa provável | Solução |
|---|---|---|
| `Failed to fetch` | Servidor parado, ou a página não está sendo servida por ele | Suba `python demo_server.py` e abra `http://localhost:8000`; no Codespaces, mantenha o terminal aberto |
| Erro **404** ao ler a foto | Outro programa responde na porta (ex.: servidor estático) | Pare o outro servidor ou troque a porta |
| **503** "OCR indisponível" | Tesseract ausente/fora do PATH | Instale e reinicie o terminal (seção 5.1) |
| Erro de **CORS** no console do navegador | Front e serviço em endereços diferentes | Seção 5.2 |
| Resultado diferente do PDF | Versões diferentes do Tesseract/OpenCV ou sem idioma `por` | Seção 8 |
| Link do Codespaces dá 404 | Porta privada ou cookies bloqueados no navegador | Porta pública, outro navegador, permitir cookies do `github.dev` |
