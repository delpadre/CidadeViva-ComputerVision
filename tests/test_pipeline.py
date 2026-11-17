
import json
import os
import tempfile
import unittest

from evaluate import evaluate
from synthetic.generate import generate


class TestEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        generate(n=4, out_dir=cls.tmp.name, seed=7)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_metrics_thresholds(self):
        m = evaluate(self.tmp.name)
        self.assertEqual(m["n_documentos"], 12)
        self.assertGreaterEqual(m["acerto_empresa_%"], 95)
        self.assertGreaterEqual(m["endereco_100%_correto_%"], 85)
        self.assertEqual(m["falhas_silenciosas"], 0)

    def test_distinguishes_target_from_decoy(self):
        from citizen_vision import process_image
        gt = json.load(open(os.path.join(self.tmp.name, "enel_000.json")))
        r = process_image(os.path.join(self.tmp.name, "enel_000.jpg"))
        self.assertEqual(r.address["cep"], gt["address"]["cep"])  # não pegou cobrança/sede


if __name__ == "__main__":
    unittest.main()
