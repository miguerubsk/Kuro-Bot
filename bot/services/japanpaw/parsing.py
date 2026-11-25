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
    paste_url = _paste_url(soup)
    article = _own_article(soup, post_id)
    classes = article.get("class", []) if article else []
    page_title = soup.title.get_text(strip=True) if soup.title else ""
    return PostInfo(
        post_id=post_id, title=_title(soup, fallback_title) or page_title, url=url, paste_url=paste_url,
        paste_id=PASTE_RE.match(paste_url).group(1) if paste_url else None,
        airing="category-en-emision" in classes or _ficha_says_airing(article), label=_label(page_title),
        movie="category-pelicula" in classes,
    )


def _paste_url(soup) -> str | None:
    """El enlace al paste: el del botón de descarga o, si no, el primero que lo sea."""
    a = soup.select_one("a.DownloadV1[href]")
    if a and PASTE_RE.match(a["href"]):
        return a["href"]
    return next((a["href"] for a in soup.find_all("a", href=True) if PASTE_RE.match(a["href"])), None)


def _own_article(soup, post_id: int):
    """La página incluye <article> de posts relacionados: hay que mirar el del propio post."""
    return soup.select_one(f"article.post-{post_id}") or soup.find(class_=re.compile(rf"\bpost-{post_id}\b"))


def _label(page_title: str) -> str:
    """Calidad y episodios del título de la página: «Web 1080p [21/24]» (o lo que haya)."""
    parts = []
    m = re.search(r"\b((?:BD|DL|Web|WEB|TV|DVD)\b[^\[\]]*?\d{3,4}p)", page_title)
    if m:
        parts.append(m.group(1).strip())
    m = re.search(r"\[(\d+\s*/\s*(?:\d+|\?+))\]", page_title)
    if m:
        parts.append(f"[{m.group(1).replace(' ', '')}]")
    return " ".join(parts)


def _title(soup, fallback_title: str) -> str:
    if fallback_title:
        return fallback_title
    h1 = soup.select_one("h1")
    return h1.get_text(strip=True) if h1 else ""


def _ficha_says_airing(article) -> bool:
    """
    La web no siempre pone la categoría «en emisión» al post, pero la ficha
    sí lo dice («Episodios: En emisión»). Solo la del propio post (no las de
    los relacionados).
    """
    if article is None:
        return False
    return "emisi" in (parse_details(str(article)).episodes or "").lower()


def parse_details(content_html: str) -> Details:
    soup = BeautifulSoup(content_html or "", "html.parser")
    d = Details(cover_url=_cover_url(soup), synopsis=_synopsis(_synopsis_cell(soup)))
    for attr, value in _fields(soup):
        setattr(d, attr, value)
    return d


def _cover_url(soup) -> str:
    """La portada es la primera imagen que no sea un icono de la tabla (de AniList, la grande)."""
    for img in soup.find_all("img", src=True):
        src = img["src"]
        if not _ICON_RE.search(src) and is_cover_url(src):
            return re.sub(r"/cover/(?:small|medium)/", "/cover/large/", src)
    return ""


def _fields(soup):
    """(atributo de Details, valor) de cada fila «dato | valor» de la tabla que se reconoce."""
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 2:
            continue
        attr = _FIELD_KEYS.get(tds[-2].get_text(" ", strip=True).lower())
        if attr:
            yield attr, tds[-1].get_text(" ", strip=True)


def _synopsis_cell(soup):
    """La sinopsis va en la fila de debajo del botón de descarga; plan B: el primer párrafo largo."""
    a = soup.select_one("a.DownloadV1")
    tr = a.find_parent("tr") if a else None
    nxt = tr.find_next_sibling("tr") if tr else None
    cell = nxt.find("td") if nxt else None
    if cell is None:
        cell = next((p for p in soup.find_all(["p", "td"])
                     if len(p.get_text(strip=True)) > 150 and not p.find("table")), None)
    return cell


def _synopsis(cell) -> str:
    """El texto de la celda sin las líneas que nombran la web ni el «(escrito por...)» del final."""
    if cell is None:
        return ""
    lines = [l.strip() for l in cell.get_text("\n").split("\n") if l.strip()]
    text = " ".join(l for l in lines if not re.search(r"japan[- ]?paw", l, re.I))
    return _CREDIT_RE.sub("", text).strip()
