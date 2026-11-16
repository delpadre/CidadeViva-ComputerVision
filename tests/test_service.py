import os
import unittest

from citizen_vision.municipio import resolve_municipio
from citizen_vision.service import ServiceError, extract_from_bytes

ROOT = os.path.dirname(os.path.dirname(__file__))
ADDR = dict(logradouro="RUA A", numero="1", bairro="CENTRO", cidade="CAMPINAS", uf="SP", cep="13010-000")


class TestMunicipio(unittest.TestCase):
    def test_offline_uses_invoice_city(self):
        m = resolve_municipio(ADDR)
        self.assertEqual((m["municipio"], m["uf"], m["ibge"], m["fonte"]), ("CAMPINAS", "SP", None, "fatura"))

    def test_online_gets_ibge(self):
        fake = lambda cep: {"localidade": "Campinas", "uf": "SP", "ibge": "3509502"}
        m = resolve_municipio(ADDR, online=True, lookup=fake)
        self.assertEqual((m["ibge"], m["fonte"], m["confere_cep"]), ("3509502", "viacep", True))

    def test_online_detects_cep_city_mismatch(self):
        fake = lambda cep: {"localidade": "Santos", "uf": "SP", "ibge": "3548500"}
        self.assertFalse(resolve_municipio(ADDR, online=True, lookup=fake)["confere_cep"])

    def test_online_lookup_failure_falls_back_to_invoice(self):
        self.assertEqual(resolve_municipio(ADDR, online=True, lookup=lambda c: None)["fonte"], "fatura")


class TestService(unittest.TestCase):
    def test_errors(self):
        for data, status in ((b"", 400), (b"isto nao e imagem", 400), (b"0" * (8 * 1024 * 1024 + 1), 413)):
            with self.assertRaises(ServiceError) as cm:
                extract_from_bytes(data)
            self.assertEqual(cm.exception.status, status)

    def test_extracts_from_sample(self):
        with open(os.path.join(ROOT, "docs", "samples", "sabesp_000.jpg"), "rb") as f:
            out = extract_from_bytes(f.read())
        self.assertEqual(out["company"], "sabesp")
        self.assertEqual(out["municipio"]["municipio"], out["address"]["cidade"])
        self.assertTrue(out["needs_review"])  # humano sempre confirma


if __name__ == "__main__":
    unittest.main()
