"""Lectura del HTML de la web: enlace de descarga de un post y su ficha."""

import re
import urllib.parse

from bs4 import BeautifulSoup

from .models import Details, PostInfo

ALLOWED_HOSTS = ("japanpaw.com", "japan-paw.net")
COVER_HOSTS = ALLOWED_HOSTS + ("anilist.co",)
PASTE_RE = re.compile(r"^https?://paste\.japan-paw\.net/\?v=(\d+)")

_CREDIT_RE = re.compile(r"\s*[\[(](?:escrito|written|fuente|source)[^\])]*[\])]\s*$", re.I)
_ICON_RE = re.compile(r"switchmodo\.com|/(?:Season|Capitulos\d*|Downicon\w*|DownloadIcon\w*)\.png$", re.I)
_FIELD_KEYS = {
    "episodios": "episodes", "temporada": "season", "fecha de estreno": "premiere",
    "géneros": "genres", "generos": "genres", "especificaciones del vídeo": "video",
    "especificaciones del video": "video",
}


def _host_in(url: str, hosts, schemes=("http", "https")) -> bool:
    try:
        p = urllib.parse.urlparse(url)
    except ValueError:
        return False
    host = (p.hostname or "").lower()
    return p.scheme in schemes and any(host == h or host.endswith("." + h) for h in hosts)


def is_allowed_url(url: str) -> bool:
    return _host_in(url, ALLOWED_HOSTS)


def is_cover_url(url: str) -> bool:
    return _host_in(url, COVER_HOSTS, schemes=("https",))


def clean_title(title: str) -> str:
    """Quita el " (#1234)" que se añade a los títulos repetidos."""
    return re.sub(r"\s+\(#\d+\)$", "", title)


def parse_post_html(page_html: str, post_id: int, url: str, fallback_title: str = "") -> PostInfo:
    soup = BeautifulSoup(page_html, "html.parser")

    paste_url = None
    a = soup.select_one("a.DownloadV1[href]")
    if a and PASTE_RE.match(a["href"]):
        paste_url = a["href"]
    else:
        paste_url = next((a["href"] for a in soup.find_all("a", href=True) if PASTE_RE.match(a["href"])), None)
    paste_id = PASTE_RE.match(paste_url).group(1) if paste_url else None

    # La página incluye <article> de posts relacionados: hay que mirar el del propio post
    article = soup.select_one(f"article.post-{post_id}") or soup.find(class_=re.compile(rf"\bpost-{post_id}\b"))
    classes = article.get("class", []) if article else []

    page_title = soup.title.get_text(strip=True) if soup.title else ""
    label_parts = []
    m = re.search(r"\b((?:BD|DL|Web|WEB|TV|DVD)\b[^\[\]]*?\d{3,4}p)", page_title)
    if m:
        label_parts.append(m.group(1).strip())
    m = re.search(r"\[(\d+\s*/\s*(?:\d+|\?+))\]", page_title)
    if m:
        label_parts.append(f"[{m.group(1).replace(' ', '')}]")

    title = fallback_title
    h1 = soup.select_one("h1")
    if not title and h1:
        title = h1.get_text(strip=True)

    return PostInfo(
        post_id=post_id, title=title or page_title, url=url, paste_url=paste_url, paste_id=paste_id,
        airing="category-en-emision" in classes, label=" ".join(label_parts),
        movie="category-pelicula" in classes,
    )


def parse_details(content_html: str) -> Details:
    soup = BeautifulSoup(content_html or "", "html.parser")
    d = Details()
    # la portada es la primera imagen que no sea un icono de la tabla
    for img in soup.find_all("img", src=True):
        src = img["src"]
        if _ICON_RE.search(src) or not is_cover_url(src):
            continue
        d.cover_url = re.sub(r"/cover/(?:small|medium)/", "/cover/large/", src)  # AniList: la grande
        break
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 2:
            continue
        attr = _FIELD_KEYS.get(tds[-2].get_text(" ", strip=True).lower())
        if attr:
            setattr(d, attr, tds[-1].get_text(" ", strip=True))
    # la sinopsis va en la fila de debajo del botón de descarga
    a = soup.select_one("a.DownloadV1")
    cell = None
    if a:
        tr = a.find_parent("tr")
        nxt = tr.find_next_sibling("tr") if tr else None
        cell = nxt.find("td") if nxt else None
    if cell is None:  # plan B: el primer párrafo largo
        cell = next((p for p in soup.find_all(["p", "td"])
                     if len(p.get_text(strip=True)) > 150 and not p.find("table")), None)
    if cell is not None:
        lines = [l.strip() for l in cell.get_text("\n").split("\n") if l.strip()]
        text = " ".join(l for l in lines if not re.search(r"japan[- ]?paw", l, re.I))
        d.synopsis = _CREDIT_RE.sub("", text).strip()
    return d
