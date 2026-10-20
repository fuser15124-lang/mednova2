import httpx
import xml.etree.ElementTree as ET
from fastapi import HTTPException
from app.config import settings
BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

async def search_pubmed(query: str, page: int = 1, page_size: int = 10):
    query = query.strip()
    if not query:
        raise HTTPException(422, "Search query cannot be empty")
    page = max(1, page); page_size = min(max(1, page_size), 25)
    common = {"db": "pubmed", "tool": settings.ncbi_tool}
    if settings.ncbi_email: common["email"] = settings.ncbi_email
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(BASE + "esearch.fcgi", params={**common, "term": query, "retstart": (page-1)*page_size, "retmax": page_size, "retmode": "json", "sort": "relevance"})
            r.raise_for_status(); search = r.json()["esearchresult"]
            ids = search.get("idlist", [])
            if not ids: return {"query": query, "page": page, "total": int(search.get("count", 0)), "results": []}
            r = await client.get(BASE + "esummary.fcgi", params={**common, "id": ",".join(ids), "retmode": "json"})
            r.raise_for_status(); summary = r.json()["result"]
            r = await client.get(BASE + "efetch.fcgi", params={**common, "id": ",".join(ids), "rettype": "abstract", "retmode": "xml"})
            r.raise_for_status(); raw = r.text
        abstracts = {}
        try:
            root = ET.fromstring(raw)
            for article in root.findall(".//PubmedArticle"):
                pmid_el = article.find(".//PMID")
                if pmid_el is None or not pmid_el.text: continue
                parts = [" ".join((el.text or "").split()) for el in article.findall(".//Abstract/AbstractText")]
                abstracts[pmid_el.text.strip()] = " ".join(x for x in parts if x)
        except ET.ParseError:
            abstracts = {}
        results=[]
        for pmid in ids:
            item=summary.get(pmid, {})
            results.append({"pmid": pmid, "title": item.get("title", "Untitled"), "authors": [a.get("name", "") for a in item.get("authors", [])[:6]], "journal": item.get("fulljournalname") or item.get("source"), "pubdate": item.get("pubdate"), "doi": next((x.get("value") for x in item.get("articleids", []) if x.get("idtype")=="doi"), None), "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", "abstract": abstracts.get(pmid, "Abstract text was not returned by this response; open the PubMed record.")})
        return {"query": query, "page": page, "total": int(search.get("count", 0)), "results": results}
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise HTTPException(502, "PubMed is temporarily unavailable. Please retry later.") from exc
