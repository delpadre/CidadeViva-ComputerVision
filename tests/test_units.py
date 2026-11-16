import unittest

from citizen_vision.config import normalize
from citizen_vision.extract import find_cep, parse_inline, parse_multiline, parse_street_bairro
from citizen_vision.validate import validate_address


class TestNormalize(unittest.TestCase):
    def test_accents_and_case(self):
        self.assertEqual(normalize("São Paulo – Av.  Brasil"), "SAO PAULO - AV. BRASIL")


class TestCep(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(find_cep("CEP 01310-100"), "01310-100")

    def test_ocr_letter_confusion(self):
        self.assertEqual(find_cep("CEP O1310-1O0"), "01310-100")

    def test_none(self):
        self.assertIsNone(find_cep("sem cep aqui"))


class TestParsers(unittest.TestCase):
    def test_multiline(self):
        a = parse_multiline(["RUA DAS ACACIAS, 120", "CENTRO", "CAMPINAS - SP", "CEP 13010-000"])
        self.assertEqual((a["logradouro"], a["numero"], a["bairro"], a["cidade"], a["uf"], a["cep"]),
                         ("RUA DAS ACACIAS", "120", "CENTRO", "CAMPINAS", "SP", "13010-000"))

    def test_street_bairro(self):
        a = parse_street_bairro(["AVENIDA BRASIL, 55 - MOOCA", "CEP 03100-000 - SAO PAULO/SP"])
        self.assertEqual((a["numero"], a["bairro"], a["cidade"], a["uf"]), ("55", "MOOCA", "SAO PAULO", "SP"))

    def test_inline_with_complement(self):
        a = parse_inline(["RUA AUGUSTA, 900, APTO 12", "LAPA - CURITIBA - PR - CEP 80000-000"])
        self.assertEqual((a["logradouro"], a["numero"], a["bairro"], a["cidade"], a["uf"], a["cep"]),
                         ("RUA AUGUSTA", "900", "LAPA", "CURITIBA", "PR", "80000-000"))


class TestUf(unittest.TestCase):
    def test_ocr_noise(self):
        from citizen_vision.extract import _clean_uf, _split_city_uf
        self.assertEqual(_clean_uf("R)"), "RJ")
        self.assertEqual(_split_city_uf("RIO DE JANEIRO/R)"), ("RIO DE JANEIRO", "RJ"))
        self.assertEqual(_clean_uf("ZZ"), "")


class TestSuspiciousFields(unittest.TestCase):
    def test_garbage_in_city_and_bairro_is_flagged(self):
        from citizen_vision.validate import check_fields
        a = dict(logradouro="RUA A", numero="1", bairro="CEP 58127-0082", cidade="DESCRICAO VALOR (R$)", uf="", cep="")
        warnings, fields = check_fields(a)
        self.assertEqual(set(fields), {"uf", "cep", "cidade", "bairro"})

    def test_valid_address_has_no_flags(self):
        from citizen_vision.validate import check_fields
        a = dict(logradouro="RUA 7 DE SETEMBRO", numero="1", bairro="VILA D'AVILA", cidade="SAO PAULO", uf="SP", cep="01000-000")
        self.assertEqual(check_fields(a), ([], []))


class TestValidate(unittest.TestCase):
    def test_ok(self):
        a = dict(logradouro="RUA A", numero="1", bairro="B", cidade="C", uf="SP", cep="01000-000")
        self.assertEqual(validate_address(a), [])

    def test_invalid(self):
        w = validate_address(dict(logradouro="RUA A", numero="", bairro="B", cidade="C", uf="XX", cep="123"))
        self.assertTrue(any("UF" in x for x in w))
        self.assertTrue(any("CEP" in x for x in w))
        self.assertTrue(any("numero" in x for x in w))


if __name__ == "__main__":
    unittest.main()
