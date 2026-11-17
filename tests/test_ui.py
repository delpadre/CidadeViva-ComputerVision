
import json
import os
import threading
import unittest
from http.server import ThreadingHTTPServer

try:
    from playwright.sync_api import sync_playwright
    HAVE_PW = True
except Exception:  # pragma: no cover
    HAVE_PW = False

from citizen_vision.service import extract_from_bytes
from demo_server import Handler

ROOT = os.path.dirname(os.path.dirname(__file__))
SAMPLE = os.path.join(ROOT, "docs", "samples", "enel_000.jpg")
with open(os.path.join(ROOT, "docs", "samples", "enel_000.json")) as _f:
    GT = json.load(_f)["address"]


@unittest.skipUnless(HAVE_PW, "playwright não instalado")
class TestConfirmationPage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        cls.pw = sync_playwright().start()
        try:
            cls.browser = cls.pw.chromium.launch()
        except Exception as e:  # sem Chromium instalado
            cls.pw.stop(); cls.srv.shutdown()
            raise unittest.SkipTest(f"chromium indisponível: {e}")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.pw.stop(); cls.srv.shutdown()

    def page(self):
        pg = self.browser.new_page(viewport={"width": 390, "height": 844})
        pg.goto(self.url)
        return pg

    def test_happy_path_prefills_edits_and_confirms(self):
        pg = self.page()
        pg.set_input_files("#file", SAMPLE); pg.click("#read")
        pg.wait_for_selector("#step-form:not([hidden])", timeout=30000)
        got = {f: pg.input_value(f"#f-{f}") for f in ("logradouro", "numero", "bairro", "cidade", "uf", "cep")}
        self.assertEqual(got, GT)
        pg.fill("#f-numero", "")
        pg.click("#confirm")
        self.assertEqual(pg.get_attribute("#f-numero", "aria-invalid"), "true")   # não confirma com campo vazio
        pg.fill("#f-numero", GT["numero"]); pg.click("#confirm")
        pg.wait_for_selector("#step-done:not([hidden])")
        self.assertIn(GT["cep"], pg.inner_text("#summary"))

    def test_doubtful_fields_are_highlighted(self):
        bad = os.path.join(ROOT, "dataset", "enel_011.jpg")
        if not os.path.exists(bad):
            self.skipTest("dataset/enel_011.jpg ausente")
        with open(bad, "rb") as fh:
            body = json.dumps(extract_from_bytes(fh.read()), ensure_ascii=False)  # foto original (falha com aviso)
        pg = self.page()
        pg.route("**/extract-address", lambda r: r.fulfill(status=200, content_type="application/json", body=body))
        pg.set_input_files("#file", bad); pg.click("#read")
        pg.wait_for_selector("#step-form:not([hidden])", timeout=30000)
        flagged = set(pg.eval_on_selector_all("input.check", "e=>e.map(x=>x.id)"))
        self.assertTrue({"f-cep", "f-uf", "f-cidade", "f-bairro"} <= flagged)
        self.assertEqual(pg.inner_text("#municipio") if pg.locator("#municipio").is_visible() else "", "")  # sem município falso

    def test_invalid_file_offers_manual_entry(self):
        pg = self.page()
        pg.set_input_files("#file", {"name": "x.jpg", "mimeType": "image/jpeg", "buffer": b"nao-e-imagem"})
        pg.click("#read")
        pg.wait_for_function("document.getElementById('status').textContent.includes('Não foi possível')", timeout=10000)
        pg.click("#manual")
        self.assertEqual(pg.input_value("#f-cep"), "")


if __name__ == "__main__":
    unittest.main()
