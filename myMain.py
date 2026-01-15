# myMain.py
from fastapi import FastAPI, Query, HTTPException
import httpx, re, json, subprocess, sys
from lxml import etree
from typing import List, Optional
from pliegos import extract_pliegos_from_entry  # 👈 nuevo import
import asyncio
# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')



app = FastAPI(
    title="PLACSP Connector",
    description="Listado de licitaciones en España + detalle + CPV + pliegos (Windows-safe con Playwright en subproceso).",
    version="1.1.0",
)

from fastapi.middleware.cors import CORSMiddleware

# Añadir esto después de crear la app
origins = [
    # Local dev
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:3000",
    "http://127.0.0.1:3000",

    # Producción (Vercel)
    "https://licita-vision-es-front-end.vercel.app",

    # (Opcional) Si pruebas desde lovable/ngrok, deja estos. Si no los usas, bórralos.
    "https://lovable.dev",
    "https://f9109a88-847c-4113-8df3-463cb9979842.lovableproject.com",
    "https://1ab90ef1b4ad.ngrok-free.app",
]


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,          # dominios permitidos
    allow_credentials=True,
    allow_methods=["*"],            # permitir todos los métodos (GET, POST, etc.)
    allow_headers=["*"],            # permitir todas las cabeceras
)


# ---------------------------
#  FEEDS BASE
# ---------------------------
FEEDS = [
    "https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_1/licitacionesPerfilesContratanteCompleto3.atom",
    "https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_640/licitacionesPerfilesContratanteCompleto3.atom",
    "https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_641/licitacionesPerfilesContratanteCompleto3.atom",
    "https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_642/licitacionesPerfilesContratanteCompleto3.atom",
    "https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3.atom",
]

NS = {"atom": "http://www.w3.org/2005/Atom"}

# ---------------------------
#  AYUDAS GEOGRÁFICAS
# ---------------------------
PROVINCIAS = {
    "andalucía", "aragón", "asturias", "baleares", "canarias", "cantabria",
    "castilla-la mancha", "castilla y león", "cataluña", "comunidad valenciana",
    "extremadura", "galicia", "madrid", "murcia", "navarra", "la rioja",
    "país vasco", "ceuta", "melilla", "españa", "spain"
}
COMUNIDADES = {
    "andalucía": ["sevilla", "cádiz", "córdoba", "jaén", "granada", "almería", "huelva", "málaga"],
    "madrid": ["madrid"],
    "cataluña": ["barcelona", "tarragona", "lleida", "gerona", "girona"],
    "valencia": ["valencia", "castellón", "alicante"],
    "galicia": ["a coruña", "lugo", "ourense", "orense", "pontevedra"],
    "castilla y león": ["valladolid", "burgos", "león", "zamora", "soria", "palencia", "segovia", "salamanca", "ávila"],
    "castilla-la mancha": ["toledo", "cuenca", "ciudad real", "albacete", "guadalajara"],
    "país vasco": ["álava", "vizcaya", "bizkaia", "guipúzcoa", "gipuzkoa"],
    "canarias": ["las palmas", "santa cruz de tenerife"],
    "aragón": ["zaragoza", "huesca", "teruel"],
    "extremadura": ["badajoz", "cáceres"],
    "murcia": ["murcia"],
    "navarra": ["navarra"],
    "cantabria": ["cantabria"],
    "asturias": ["asturias"],
    "la rioja": ["la rioja"],
    "baleares": ["islas baleares", "baleares"],
    "ceuta": ["ceuta"],
    "melilla": ["melilla"]
}

# ---------------------------
#  FUNCIONES AUXILIARES
# ---------------------------
def _text(e) -> str:
    s = e.findtext(".//atom:summary", namespaces=NS) or ""
    c = e.findtext(".//atom:content", namespaces=NS) or ""
    return f"{s} {c}".lower()

def _looks_spain(text: str) -> bool:
    return any(p in text for p in PROVINCIAS)

def _parse_importe(text: str) -> Optional[str]:
    m = re.search(r"\b\d{1,3}(?:\.\d{3})*(?:,\d{2})\b", text)
    return m.group(0) if m else None

def _parse_organo(text: str) -> Optional[str]:
    m = re.search(r"(?:órgano\s+de\s+contratación|entidad\s+adjudicadora)\s*[:\-]\s*([^\n\r;]+)", text, re.IGNORECASE)
    return m.group(1).strip() if m else None

def _parse_posible_cpv(text: str) -> Optional[str]:
    m = re.search(r"\b(\d{8})\b", text)
    return m.group(1) if m else None

# ---------------------------
#  VARIABLES GLOBALES
# ---------------------------
Licitaciones_url: list[str] = []
cpvs_licitacion: dict[str, str] = {}

# =========================================================
# 1️⃣ LICITACIONES POR COMUNIDAD
# =========================================================
# =========================================================
# 1️⃣ LICITACIONES POR COMUNIDAD (versión robusta + feed-fallback)
# =========================================================
@app.get("/licitaciones_es")
async def licitaciones_es(
    comunidades: List[str] = Query(..., description="Lista de comunidades autónomas (varias posibles)"),
    limit: int = Query(30, ge=1, le=300)
):
    """
    Obtiene licitaciones filtradas por comunidades autónomas.
    Con fallback automático si un feed devuelve HTML en vez de XML.
    """
    global Licitaciones_url
    Licitaciones_url = []

    # Normalizar comunidades
    comunidades_normalizadas = []
    for param in comunidades:
        for c in param.split(","):
            comunidades_normalizadas.append(c.strip().lower())

    # Expandir comunidades a provincias
    provincias_filtrar = []
    for c in comunidades_normalizadas:
        provincias_filtrar.extend(COMUNIDADES.get(c, [c]))

    items = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        for feed_url in FEEDS:
            try:
                r = await client.get(feed_url)
                content = r.content

                # ⚠️ Validación — si devuelve HTML en lugar del feed Atom, ignorar
                if b"<feed" not in content[:2000].lower():
                    print(f"⚠️ Feed no válido (HTML devuelto). Ignorando → {feed_url}")
                    continue

                xml = etree.fromstring(content)
                entries = xml.xpath("//atom:entry", namespaces=NS)

                for e in entries:
                    title = e.findtext(".//atom:title", namespaces=NS) or ""
                    updated = e.findtext(".//atom:updated", namespaces=NS) or ""
                    link_el = e.find(".//atom:link", namespaces=NS)
                    url = link_el.attrib.get("href") if link_el is not None else None

                    if not url:
                        continue

                    blob = _text(e)

                    # Filtro por provincias
                    if not any(p.lower() in blob for p in provincias_filtrar):
                        continue

                    items.append({
                        "title": title.strip(),
                        "updated": updated,
                        "url": url,
                        "organo": _parse_organo(blob),
                        "importe": _parse_importe(blob),
                        "cpv_guess": _parse_posible_cpv(blob),
                        "feed_origen": feed_url
                    })

                    Licitaciones_url.append(url)

                    # Límite alcanzado
                    if len(items) >= limit:
                        break

                if len(items) >= limit:
                    break

            except Exception as e:
                print(f"⚠️ Error leyendo feed {feed_url}: {e}")
                continue

    if not Licitaciones_url:
        raise HTTPException(
            status_code=404,
            detail="No se encontraron licitaciones en las comunidades solicitadas (o los feeds están temporalmente caídos)."
        )

    return {"count": len(items), "results": items}


# =========================================================
# 2️⃣ SCRAPER DE CPVs (usa subproceso Playwright)
# =========================================================
def _scrape_via_subprocess(url: str, timeout_sec: int = 75) -> dict:
    """
    Lanza run_scraper_subprocess.py (proceso separado) y devuelve el dict con los datos del detalle.
    """
    try:
        completed = subprocess.run(
            [sys.executable, "run_scraper_subprocess.py", url],
            capture_output=True, text=True, timeout=timeout_sec
        )

        stdout = (completed.stdout or "").strip()
        stderr = (completed.stderr or "").strip()

        # 🧩 Mostrar en consola si hay error
        if stderr:
            print(f"⚠️ STDERR de Playwright: {stderr[:300]}")

        # 🧩 A veces se imprimen líneas vacías o mensajes antes del JSON → limpiamos
        json_start = stdout.find("{")
        json_end = stdout.rfind("}")
        if json_start != -1 and json_end != -1:
            stdout = stdout[json_start:json_end + 1]

        if not stdout:
            return {"error": "stdout vacío", "stderr": stderr}

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as e:
            print(f"⚠️ Error parseando JSON del subproceso: {e}")
            print(f"Salida capturada:\n{stdout[:500]}")
            return {"error": f"JSON inválido en subproceso ({e})", "raw": stdout}

        return data

    except subprocess.TimeoutExpired:
        return {"error": f"Timeout al scrapear {url}"}
    except Exception as e:
        return {"error": str(e)}


@app.get("/cpv_licitaciones")
def cpv_licitaciones():
    global Licitaciones_url, cpvs_licitacion
    if not Licitaciones_url:
        raise HTTPException(status_code=400, detail="Primero ejecuta /licitaciones_es para obtener URLs.")

    cpvs_licitacion = {}
    for url in Licitaciones_url:
        print(f"🟢 Procesando: {url}")
        data = _scrape_via_subprocess(url)
        cpvs_licitacion[url] = data.get("cpv", "") if isinstance(data, dict) else ""
        if "error" in data:
            print(f"⚠️ Error procesando {url}: {data['error']}")

    return {"count": len(cpvs_licitacion), "results": cpvs_licitacion}

# =========================================================
# 3️⃣ LISTAR TODOS LOS CPVs DISPONIBLES (para desplegable)
# =========================================================
@app.get("/cpv_disponibles")
def cpv_disponibles():
    global cpvs_licitacion
    if not cpvs_licitacion:
        raise HTTPException(status_code=400, detail="Primero ejecuta /cpv_licitaciones para poblar CPVs.")

    todos = []
    for v in cpvs_licitacion.values():
        # Captura más robusta: número + texto asociado
        matches = re.findall(r"\b\d{8}\s*[-–—]?\s*[^\d\n]+", v)
        todos.extend([m.strip().replace(" ,", ",") for m in matches if m.strip()])

    unicos = sorted(set(todos))
    return {"count": len(unicos), "cpvs": unicos}


# =========================================================
# 4️⃣ FILTRAR LICITACIONES POR CPV (multi-selección)
# =========================================================
@app.get("/filtrar_cpvs")
def filtrar_cpvs(cpvs: List[str] = Query(..., description="Lista de CPVs a buscar (OR).")):
    global cpvs_licitacion
    if not cpvs_licitacion:
        raise HTTPException(status_code=400, detail="Primero ejecuta /cpv_licitaciones para poblar CPVs.")

    seleccionados = set(c.strip() for c in cpvs if c.strip())
    resultados: dict[str, list[str]] = {}

    for url, cpv_str in cpvs_licitacion.items():
        cpv_list = re.findall(r"\b\d{8}[^,]*?(?=\s*\d{8}|\Z)", cpv_str)
        cpv_list = [c.strip() for c in cpv_list if c.strip()]
        if any(c in cpv_list for c in seleccionados):
            resultados[url] = cpv_list

    return {"count": len(resultados), "results": resultados}

# =========================================================
# 5️⃣ DETALLE DE LICITACIÓN INDIVIDUAL
# =========================================================
@app.get("/detalle_licitacion")
async def detalle_licitacion(
    url: str = Query(..., description="URL detalle HTML de la licitación"),
    feed: str = Query(..., description="Feed ATOM donde está la licitación")
):
    """
    Devuelve:
    - título, entidad, CPV, importe (Playwright)
    - pliegos extraídos del XML real del feed
    """

    # 1️⃣ Ejecutar Playwright (detalle HTML)
    data = _scrape_via_subprocess(url)

    if isinstance(data, dict) and "error" in data:
        raise HTTPException(status_code=502, detail=f"Error Playwright: {data['error']}")

    # 2️⃣ Extraer pliegos desde el feed XML
    try:
        pliegos = await extract_pliegos_from_entry(entry_url=url, feed_doc_url=feed)
        data["pliegos_xml"] = pliegos
    except Exception as e:
        print(f"⚠️ Error extrayendo pliegos: {e}")
        data["pliegos_xml"] = []

    return data




















