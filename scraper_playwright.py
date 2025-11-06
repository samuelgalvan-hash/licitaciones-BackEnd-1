# scraper_playwright.py
from playwright.sync_api import sync_playwright
import time

def scrape_licitacion(url: str) -> dict:
    """
    Abre el detalle de la licitación, localiza el iframe real '/buscadores/detalle/'
    y extrae campos: título, entidad, cpv, importe y enlaces PDF (pliegos).
    Devuelve un dict con estos campos.
    """
    data = {"url": url}

    with sync_playwright() as p:
        # Ajusta headless=True si no quieres ver el navegador
        browser = p.chromium.launch(headless=True, args=["--ignore-certificate-errors"])
        page = browser.new_page()
        page.goto(url, timeout=90_000)

        # Tiempo para que se carguen frames
        time.sleep(3)

        # Buscar el iframe de detalle
        target_frame = None
        for frame in page.frames:
            if "/buscadores/detalle/" in (frame.url or ""):
                target_frame = frame
                break
        if not target_frame:
            target_frame = page.main_frame  # fallback

        # Espera suave a que aparezcan los campos
        try:
            target_frame.wait_for_selector("table", timeout=20_000)
        except Exception:
            pass

        # Selectores (robustos a sufijos dinámicos)
        def read_span_like(fragment_id: str) -> str:
            try:
                return target_frame.locator(f"span[id*='{fragment_id}']").first.inner_text().strip()
            except Exception:
                return ""

        data["title"] = read_span_like("text_ObjetoContrato")
        data["entidad"] = read_span_like("text_UbicacionOrganica")
        data["cpv"] = read_span_like("text_CPV")
        data["importe"] = read_span_like("text_Presupuesto")

        # Pliegos PDF (enlaces que terminen en .pdf)
        try:
            pliegos = []
            pdfs = target_frame.locator("a[href$='.pdf']")
            for i in range(pdfs.count()):
                href = pdfs.nth(i).get_attribute("href")
                if href:
                    pliegos.append(href)
            data["pliegos"] = pliegos
        except Exception:
            data["pliegos"] = []

        browser.close()
    return data

# Permite testearlo a mano:
#   python scraper_playwright.py "https://contrataciondelestado.es/wps/poc?uri=deeplink:detalle_licitacion&idEvl=XXXX"
if __name__ == "__main__":
    import sys, json
    u = sys.argv[1]
    print(json.dumps(scrape_licitacion(u), ensure_ascii=False))
