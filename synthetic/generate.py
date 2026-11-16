
from __future__ import annotations

import argparse
import json
import os
import random

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 1240, 1754
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

STREETS = ["RUA DAS ACACIAS", "AVENIDA BRASIL", "RUA DOS ANDRADAS", "RUA CONSELHEIRO NEBIAS",
           "AVENIDA PAULISTA", "RUA AUGUSTA", "RUA SETE DE SETEMBRO", "TRAVESSA DAS FLORES",
           "RUA QUINZE DE NOVEMBRO", "ALAMEDA SANTOS", "RUA DOS PINHEIROS", "AVENIDA DO ESTADO"]
BAIRROS = ["CENTRO", "JARDIM AMERICA", "VILA MARIANA", "MOOCA", "BOM RETIRO", "SANTANA",
           "LAPA", "PINHEIROS", "TATUAPE", "IPIRANGA", "BELA VISTA", "SAUDE"]
CITIES = [("SAO PAULO", "SP"), ("CAMPINAS", "SP"), ("RIO DE JANEIRO", "RJ"),
          ("BELO HORIZONTE", "MG"), ("CURITIBA", "PR"), ("PORTO ALEGRE", "RS"), ("SALVADOR", "BA")]
COMPLEMENTS = ["APTO 12", "BLOCO B", "CASA 2", "FUNDOS", "SALA 31"]


def fake_address(rng: random.Random) -> dict:
    city, uf = rng.choice(CITIES)
    return dict(logradouro=rng.choice(STREETS), numero=str(rng.randint(1, 3999)),
                bairro=rng.choice(BAIRROS), cidade=city, uf=uf,
                cep=f"{rng.randint(1000, 99999):05d}-{rng.randint(0, 999):03d}")


def _f(size, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT, size)


def _lines_for(layout: str, a: dict, rng: random.Random) -> list[str]:
    if layout == "multiline":
        return [f"{a['logradouro']}, {a['numero']}", a["bairro"], f"{a['cidade']} - {a['uf']}", f"CEP {a['cep']}"]
    if layout == "street_bairro":
        return [f"{a['logradouro']}, {a['numero']} - {a['bairro']}", f"CEP {a['cep']} - {a['cidade']}/{a['uf']}"]
    return [f"{a['logradouro']}, {a['numero']}, {rng.choice(COMPLEMENTS)}",
            f"{a['bairro']} - {a['cidade']} - {a['uf']} - CEP {a['cep']}"]


def _block(d, y, label, lines, x=70):
    d.text((x, y), label, font=_f(24, True), fill=(90, 90, 90))
    y += 40
    for ln in lines:
        d.text((x, y), ln, font=_f(30), fill=(0, 0, 0))
        y += 44
    return y + 30


def _table(d, y, rng, rows, unit):
    d.rectangle([70, y, W - 70, y + 44], fill=(225, 225, 225))
    d.text((85, y + 8), "Descricao", font=_f(24, True), fill=(0, 0, 0))
    d.text((W - 330, y + 8), "Valor (R$)", font=_f(24, True), fill=(0, 0, 0))
    y += 56
    for r in rows:
        d.text((85, y), f"{r} {rng.randint(10, 400)} {unit}", font=_f(26), fill=(30, 30, 30))
        d.text((W - 330, y), f"{rng.randint(10, 450)},{rng.randint(0, 99):02d}", font=_f(26), fill=(30, 30, 30))
        y += 46
    return y + 20


TEMPLATES = {
    "enel": dict(color=(0, 90, 170), layout="multiline", head="ENEL", sub="Distribuicao Sao Paulo",
                 title="CONTA DE ENERGIA ELETRICA", anchor="ENDERECO DA UNIDADE CONSUMIDORA",
                 rows=["Consumo kWh", "Bandeira tarifaria", "Iluminacao publica"], unit="kWh", decoy_first=True),
    "sabesp": dict(color=(0, 120, 70), layout="street_bairro", head="SABESP", sub="Companhia de Saneamento",
                   title="CONTA DE AGUA E ESGOTO", anchor="ENDERECO DO IMOVEL",
                   rows=["Agua - consumo", "Esgoto", "Hidrometro leitura"], unit="m3", decoy_first=False),
    "claro": dict(color=(200, 20, 30), layout="inline", head="CLARO", sub="Residencial",
                  title="FATURA CLARO - INTERNET E TV", anchor="ENDERECO DE ENTREGA DA FATURA",
                  rows=["Internet 500 Mbps", "TV por assinatura", "Ponto adicional"], unit="un", decoy_first=True),
}


def render_flat(company: str, target: dict, rng: random.Random) -> Image.Image:
    t = TEMPLATES[company]
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 170], fill=t["color"])
    d.text((70, 40), t["head"], font=_f(72, True), fill="white")
    d.text((70, 122), t["sub"], font=_f(26), fill="white")
    d.text((70, 215), t["title"], font=_f(34, True), fill=(20, 20, 20))
    d.text((70, 275), f"CLIENTE TESTE {rng.randint(1, 999):03d}", font=_f(28), fill=(0, 0, 0))

    decoy = fake_address(rng)
    decoy_lines = _lines_for(t["layout"], decoy, rng)
    target_lines = _lines_for(t["layout"], target, rng)
    y = 350
    blocks = [("ENDERECO DE COBRANCA", decoy_lines), (t["anchor"], target_lines)]
    if not t["decoy_first"]:
        blocks.reverse()
    for label, lns in blocks:
        y = _block(d, y, label, lns)
    y = _table(d, y + 20, rng, t["rows"], t["unit"])
    d.text((70, y + 20), f"Vencimento: {rng.randint(1, 28):02d}/12/2026    Total: R$ {rng.randint(80, 900)},{rng.randint(0, 99):02d}",
           font=_f(30, True), fill=(0, 0, 0))
    sede = fake_address(rng)
    d.text((70, H - 120), f"SEDE - {sede['logradouro']}, {sede['numero']} - {sede['cidade']}/{sede['uf']} - CEP {sede['cep']}",
           font=_f(22), fill=(110, 110, 110))
    return img


def simulate_photo(flat: Image.Image, rng: random.Random, hard: bool = False) -> np.ndarray:
    """Coloca a folha sobre uma mesa escura com perspectiva, rotação, sombra, ruído e desfoque."""
    page = cv2.cvtColor(np.array(flat), cv2.COLOR_RGB2BGR)
    CW, CH = 1800, 2300
    base = np.array([rng.randint(25, 70), rng.randint(35, 80), rng.randint(45, 95)], dtype=np.float32)
    bg = np.ones((CH, CW, 3), np.float32) * base
    bg += np.random.default_rng(rng.randint(0, 10**6)).normal(0, 8, (CH, CW, 1))
    jit = 70 if not hard else 110
    ox, oy = (CW - W) / 2, (CH - H) / 2
    src = np.float32([[0, 0], [W, 0], [W, H], [0, H]])
    dst = np.float32([[ox, oy], [ox + W, oy], [ox + W, oy + H], [ox, oy + H]])
    dst += np.float32([[rng.uniform(-jit, jit), rng.uniform(-jit, jit)] for _ in range(4)])
    ang = rng.uniform(-6, 6)
    rot = cv2.getRotationMatrix2D((CW / 2, CH / 2), ang, 1.0)
    dst = cv2.transform(dst.reshape(1, 4, 2), rot).reshape(4, 2).astype(np.float32)
    m = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(page, m, (CW, CH), flags=cv2.INTER_CUBIC)
    mask = cv2.warpPerspective(np.full((H, W), 255, np.uint8), m, (CW, CH))
    out = np.where(mask[..., None] > 0, warped.astype(np.float32), bg)

    # iluminação irregular (gradiente + sombra suave)
    gx = np.linspace(rng.uniform(0.75, 1.0), rng.uniform(0.9, 1.1), CW, dtype=np.float32)
    gy = np.linspace(rng.uniform(0.85, 1.05), rng.uniform(0.8, 1.0), CH, dtype=np.float32)
    light = gy[:, None] * gx[None, :]
    if hard:
        cx, cy = rng.randint(400, 1400), rng.randint(500, 1800)
        yy, xx = np.mgrid[0:CH, 0:CW]
        light *= 1 - 0.35 * np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * 300.0 ** 2)))
    out = out * light[..., None]
    out += np.random.default_rng(rng.randint(0, 10**6)).normal(0, 6 if not hard else 12, out.shape)
    out = np.clip(out, 0, 255).astype(np.uint8)
    k = 3 if not hard else 5
    return cv2.GaussianBlur(out, (k, k), 0)


def generate(n: int, out_dir: str, seed: int = 42, hard_ratio: float = 0.3) -> int:
    os.makedirs(out_dir, exist_ok=True)
    rng = random.Random(seed)
    count = 0
    for company in TEMPLATES:
        for i in range(n):
            target = fake_address(rng)
            flat = render_flat(company, target, rng)
            hard = rng.random() < hard_ratio
            photo = simulate_photo(flat, rng, hard=hard)
            doc_id = f"{company}_{i:03d}"
            flat.save(os.path.join(out_dir, f"{doc_id}_flat.png"))
            cv2.imwrite(os.path.join(out_dir, f"{doc_id}.jpg"), photo, [cv2.IMWRITE_JPEG_QUALITY, 88])
            with open(os.path.join(out_dir, f"{doc_id}.json"), "w", encoding="utf-8") as f:
                json.dump({"company": company, "hard": hard, "address": target}, f, ensure_ascii=False, indent=2)
            count += 1
    return count


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10, help="documentos por empresa")
    ap.add_argument("--out", default="data/synthetic")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    print(f"{generate(a.n, a.out, a.seed)} documentos gerados em {a.out}")
