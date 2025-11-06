import httpx
from lxml import etree
from typing import List, Dict, Optional
from urllib.parse import urljoin

NS = {"atom": "http://www.w3.org/2005/Atom"}
CODICE_NS = {
    "cac": "urn:dgpe:names:draft:codice:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:dgpe:names:draft:codice:schema:xsd:CommonBasicComponents-2",
    "cacp": "urn:dgpe:names:draft:codice-place-ext:schema:xsd:CommonAggregateComponents-2",
    "cbcp": "urn:dgpe:names:draft:codice-place-ext:schema:xsd:CommonBasicComponents-2",
}

async def _get(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.content

def _parse(xml: bytes) -> etree._Element:
    return etree.fromstring(xml)

def _find_entry_by_alternate(feed: etree._Element, entry_url: str) -> Optional[etree._Element]:
    q = f"//atom:entry[atom:link[@rel='alternate' and @href='{entry_url}'] or atom:id[text()='{entry_url}']]"
    nodes = feed.xpath(q, namespaces=NS)
    return nodes[0] if nodes else None

def _extract_docs_from_entry(entry: etree._Element) -> List[Dict]:
    # Especificación 4.9: URIs de pliegos en:
    # - LegalDocumentReference/Attachment/ExternalReference/URI  (PCAP)
    # - TechnicalDocumentReference/Attachment/ExternalReference/URI (PPT)
    # - AditionalDocumentReference/Attachment/ExternalReference/URI (otros)
    content_xml = entry.xpath("atom:content/*", namespaces=NS)
    if not content_xml:
        return []

    root = content_xml[0]
    docs = []

    # PCAP
    for uri in root.xpath(".//cac:LegalDocumentReference/cac:Attachment/cac:ExternalReference/cbc:URI/text()", namespaces=CODICE_NS):
        docs.append({"tipo": "PCAP", "url": uri})

    # PPT
    for uri in root.xpath(".//cac:TechnicalDocumentReference/cac:Attachment/cac:ExternalReference/cbc:URI/text()", namespaces=CODICE_NS):
        docs.append({"tipo": "PPT", "url": uri})

    # Otros
    for uri in root.xpath(".//cac:AditionalDocumentReference/cac:Attachment/cac:ExternalReference/cbc:URI/text()", namespaces=CODICE_NS):
        docs.append({"tipo": "OTRO", "url": uri})

    # Eliminar duplicados preservando orden
    seen = set()
    clean = []
    for d in docs:
        if d["url"] not in seen:
            seen.add(d["url"])
            clean.append(d)
    return clean

async def extract_pliegos_from_entry(entry_url: str, feed_doc_url: Optional[str] = None) -> List[Dict]:
    """
    Si se pasa feed_doc_url, busca la entry dentro del feed.
    Si no, intenta descargar la propia entry_url (algunas entradas son una página HTML y no el XML; por eso el feed ayuda).
    """
    if feed_doc_url:
        feed_xml = _parse(await _get(feed_doc_url))
        entry = _find_entry_by_alternate(feed_xml, entry_url)
        if entry is not None:
            return _extract_docs_from_entry(entry)

    # fallback: intentar que entry_url sea directamente un XML (no siempre lo es)
    try:
        entry_xml = _parse(await _get(entry_url))
        # si esto funciona, probablemente es un documento atom con una sola entrada
        entry = entry_xml.xpath("//atom:entry", namespaces=NS)
        if entry:
            return _extract_docs_from_entry(entry[0])
    except Exception:
        pass

    # si no hay forma de extraerlos, devolvemos vacío
    return []

if __name__ == "__main__":
    import sys, asyncio, json
    url = sys.argv[1]
    pliegos = asyncio.run(extract_pliegos_from_entry(url))
    print(json.dumps(pliegos, ensure_ascii=False))







