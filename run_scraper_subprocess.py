# run_scraper_subprocess.py
import sys, json
from scraper_playwright import scrape_licitacion

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Falta URL"}))
        return
    url = sys.argv[1]
    try:
        data = scrape_licitacion(url)
        # MUY IMPORTANTE: SOLO imprimimos JSON en stdout
        print(json.dumps(data, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
