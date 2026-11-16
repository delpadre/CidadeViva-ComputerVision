"""Avalia o pipeline contra o gabarito sintético.

Uso: python evaluate.py --data dataset [--limit N] [--report docs/metrics.json]
Métricas: acerto da empresa, acerto por campo, endereço 100% correto, CER e tempo.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import time

from citizen_vision import process_image
from citizen_vision.config import normalize

FIELDS = ("logradouro", "numero", "bairro", "cidade", "uf", "cep")


def levenshtein(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def cer(pred: str, truth: str) -> float:
    return levenshtein(pred, truth) / max(len(truth), 1)


def join(addr: dict) -> str:
    return normalize(" ".join(addr.get(f, "") for f in FIELDS))


def evaluate(data_dir: str, limit: int | None = None, verbose: bool = False) -> dict:
    gts = sorted(glob.glob(os.path.join(data_dir, "*.json")))
    if limit:
        gts = gts[:limit]
    n = len(gts)
    cls_ok = full_ok = false_alarms = 0
    field_ok = {f: 0 for f in FIELDS}
    cers, times, failures = [], [], []
    by_company: dict = {}
    by_diff = {"easy": [0, 0], "hard": [0, 0]}

    for gt_path in gts:
        with open(gt_path, encoding="utf-8") as fh:
            gt = json.load(fh)
        img = gt_path[:-5] + ".jpg"
        t0 = time.perf_counter()
        r = process_image(img)
        times.append(time.perf_counter() - t0)
        truth = gt["address"]
        pred = r.address or {}
        c_ok = r.company == gt["company"]
        cls_ok += c_ok
        ok_fields = {f: normalize(pred.get(f, "")) == normalize(truth[f]) for f in FIELDS}
        for f in FIELDS:
            field_ok[f] += ok_fields[f]
        all_ok = c_ok and all(ok_fields.values())
        full_ok += all_ok
        false_alarms += bool(all_ok and r.warnings)   # acertou, mas mandou o cidadão conferir
        cers.append(cer(join(pred), join(truth)))
        bc = by_company.setdefault(gt["company"], [0, 0])
        bc[0] += all_ok
        bc[1] += 1
        bd = by_diff["hard" if gt.get("hard") else "easy"]
        bd[0] += all_ok
        bd[1] += 1
        if not all_ok:
            failures.append({"id": os.path.basename(gt_path)[:-5], "company_pred": r.company,
                             "pred": pred, "truth": truth, "warnings": r.warnings})
        if verbose:
            print(("OK  " if all_ok else "FAIL"), os.path.basename(gt_path), r.company, r.warnings)

    pct = lambda a, b: round(100 * a / b, 1) if b else 0.0
    return {
        "n_documentos": n,
        "acerto_empresa_%": pct(cls_ok, n),
        "acerto_por_campo_%": {f: pct(field_ok[f], n) for f in FIELDS},
        "endereco_100%_correto_%": pct(full_ok, n),
        "por_empresa_%": {k: pct(a, b) for k, (a, b) in by_company.items()},
        "por_dificuldade_%": {k: pct(a, b) for k, (a, b) in by_diff.items()},
        "falsos_alertas": false_alarms,
        "falhas_silenciosas": sum(1 for f in failures if not f["warnings"]),
        "CER_medio": round(sum(cers) / n, 4) if n else None,
        "tempo_medio_s": round(sum(times) / n, 2) if n else None,
        "falhas": failures,
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="dataset")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--report")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    m = evaluate(a.data, a.limit, a.verbose)
    print(json.dumps({k: v for k, v in m.items() if k != "falhas"}, indent=2, ensure_ascii=False))
    print(f"falhas: {len(m['falhas'])}")
    if a.report:
        os.makedirs(os.path.dirname(a.report) or ".", exist_ok=True)
        json.dump(m, open(a.report, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
