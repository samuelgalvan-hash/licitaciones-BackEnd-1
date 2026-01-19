
# myMain.py (versión corregida con normalización y comunidades unificadas)
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx, re, json, subprocess, sys, os
from lxml import etree
from typing import List, Optional
from pliegos import extract_pliegos_from_entry
import unicodedata

# ===========================================
# 🇪🇸 UTF-8
# ===========================================
sys.stdout.reconfigure(encoding='utf-8')

# ===========================================
#  FASTAPI
# ===========================================
app = FastAPI(
    title="PLACSP Connector",
    description="Listado de licitaciones + detalle + CPV + pliegos",
    version="1.2.0",
)

# ===========================================
#  CORS
# ===========================================
origins_env = os.getenv("CORS_ORIGINS", "").strip()
if origins_env:
    allowed_origins = [o.strip() for o in origins_env.split(",") if o.strip()]
else:
    allowed_origins = [
        "http://localhost",
        "http://127.0.0.1",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://licita-vision-es-frontend-1.vercel.app",
        "https://licita-vision-es-frontend-1-git-main-samuels-projects-37ed2b28.vercel.app",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"^https://.*\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "ok", "service": "licitaciones-backend"}

# ===========================================
# FEEDS
# ===========================================
FEEDS = [
    "https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_1/licitacionesPerfilesContratanteCompleto3.atom",
    "https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_640/licitacionesPerfilesContratanteCompleto3.atom",
    "https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_641/licitacionesPerfilesContratanteCompleto3.atom",
    "https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_642/licitacionesPerfilesContratanteCompleto3.atom",
    "https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3.atom",
]
NS = {"atom": "http://www.w3.org/2005/Atom"}

# ===========================================
#  NORMALIZACIÓN ROBUSTA
# ===========================================
def normalizar(texto: str) -> str:
    if not texto:
        return ""
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = texto.replace("-", " ").replace("  ", " ")
    return texto.strip()

# ===========================================
#  PROVINCIAS / COMUNIDADES
# ===========================================
PROVINCIAS = {
    "andalucia", "aragon", "asturias", "baleares", "canarias", "cantabria",
    "castilla la mancha", "castilla y leon", "cataluna", "comunidad valenciana",
    "extremadura", "galicia", "madrid", "murcia", "navarra", "la rioja",
    "pais vasco", "ceuta", "melilla", "espana", "spain"
}

# CLAVE: unificamos "comunidad valenciana"
COMUNIDADES = {
    "andalucia": ["sevilla","cadiz","cordoba","jaen","granada","almeria","huelva","malaga"],

    "madrid": ["madrid"],

    "cataluna": ["barcelona","tarragona","lleida","gerona","girona"],

    "comunidad valenciana": ["valencia","castellon","alicante"],

    "galicia": ["a coruna","lugo","ourense","orense","pontevedra"],

    "castilla y leon": ["valladolid","burgos","leon","zamora","soria","palencia","segovia","salamanca","avila"],

    "castilla la mancha": ["toledo","cuenca","ciudad real","albacete","guadalajara"],

    "pais vasco": ["alava","vizcaya","bizkaia","guipuzcoa","gipuzkoa"],

    "canarias": ["las palmas","santa cruz de tenerife"],

    "aragon": ["zaragoza","huesca","teruel"],

    "extremadura": ["badajoz","caceres"],

    "murcia": ["murcia"],

    "navarra": ["navarra"],

    "cantabria": ["cantabria"],

    "asturias": ["asturias"],

    "la rioja": ["la rioja"],

    "baleares": ["islas baleares","baleares"],

    "ceuta": ["ceuta"],

    "melilla": ["melilla"],
}

ALIASES = {
    "valencia": "comunidad valenciana",
    "c valenciana": "comunidad valenciana",
    "comunidad de valencia": "comunidad valenciana",
    "cv": "comunidad valenciana",

    "castilla-la mancha": "castilla la mancha",
    "castilla la mancha": "castilla la mancha",
    "castilla la mancha": "castilla la mancha",

    "castilla y leon": "castilla y leon",
}

# ===========================================
# AUXILIARES DE PARSEO
# ===========================================
def _text(e) -> str:
    s = e.findtext(".//atom:summary", namespaces=NS) or ""
    c = e.findtext(".//atom:content", namespaces=NS) or ""
    return f"{s} {c}".lower()

def _parse_importe(text: str):
    m = re.search(r"\b\d{1,3}(?:\.\d{3})*(?:,\d{2})\b", text)
    return m.group(0) if m else None

def _parse_organo(text: str):
    m = re.search(r"(?:órgano\s+de\s+contratación|entidad\s+adjudicadora)\s*[:\-]\s*([^\n\r;]+)", text, re.IGNORECASE)
    return m.group(1).strip() if m else None

def _parse_posible_cpv(text: str):
    m = re.search(r"\b(\d{8})\b", text)
    return m.group(1) if m else None

Licitaciones_url = []
cpvs_licitacion = {}

# ===========================================
#  1️⃣ LICITACIONES POR COMUNIDAD
# ===========================================
@app.get("/licitaciones_es")
async def licitaciones_es(
    comunidades: List[str] = Query(...),
    limit: int = Query(30, ge=1, le=300)
):
    global Licitaciones_url
    Licitaciones_url = []

    comunidades_procesadas = []

    # Normalización + alias
    for param in comunidades:
        for c in param.split(","):
            c_norm = normalizar(c)
            if c_norm in ALIASES:
                c_norm = ALIASES[c_norm]
            comunidades_procesadas.append(c_norm)

    provincias_filtrar = []
    for c in comunidades_procesadas:
        provincias_filtrar.extend(COMUNIDADES.get(c, [c]))

    provincias_filtrar = [normalizar(p) for p in provincias_filtrar]

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/atom+xml, application/xml;q=0.9,*/*;q=0.8"
    }

    items = []

    async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
        for feed_url in FEEDS:
            try:
                r = await client.get(feed_url)
                content = r.content
                xml = etree.fromstring(content)
                entries = xml.xpath("//atom:entry", namespaces=NS)

                for e in entries:
                    blob = normalizar(_text(e))

                    if not any(p in blob for p in provincias_filtrar):
                        continue

                    link_el = e.find(".//atom:link", namespaces=NS)
                    url = link_el.attrib.get("href") if link_el is not None else None
                    if not url:
                        continue

                    items.append({
                        "title": (e.findtext(".//atom:title", namespaces=NS) or "").strip(),
                        "updated": e.findtext(".//atom:updated", namespaces=NS) or "",
                        "url": url,
                        "organo": _parse_organo(blob),
                        "importe": _parse_importe(blob),
