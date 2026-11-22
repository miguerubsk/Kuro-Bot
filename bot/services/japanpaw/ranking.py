"""
Orden de los resultados por parecido con lo buscado.

La búsqueda de WordPress encuentra el texto en cualquier parte (dentro de
otras palabras y también en la ficha) y ordena por fecha: con «Shiki», el
anime que se llama exactamente así salía detrás de «Soshiki», «Chishiki» o
«Yuyushiki», y se perdía al recortar a los primeros resultados. Aquí se
puntúa cada título y se ordena de más a menos parecido (a igualdad, se
respeta el orden de la web).
"""

import re
import unicodedata

# del más parecido al menos
EXACT, PREFIX, PHRASE, ALL_WORDS, SOME_WORDS, SUBSTRING, ELSEWHERE = range(7)


def norm(text: str) -> str:
    """minúsculas, sin tildes ni signos: «Shiki: Specials!» -> «shiki specials»"""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower().replace("’", "'")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def relevance(query: str, title: str) -> int:
    q, t = norm(query), norm(title)
    if not q:
        return ELSEWHERE
    if t == q:
        return EXACT
    if t.startswith(q + " "):
        return PREFIX
    if f" {q} " in f" {t} ":
        return PHRASE
    words = q.split()
    title_words = set(t.split())
    found = sum(w in title_words for w in words)
    if found == len(words):
        return ALL_WORDS
    if found and len(words) > 1:
        return SOME_WORDS
    if q.replace(" ", "") in t.replace(" ", ""):
        return SUBSTRING
    return ELSEWHERE   # solo sale en la ficha, no en el título


def rank(query: str, items: list, title=lambda x: x.title) -> list:
    """Ordenados por relevancia; a igualdad, en el orden original (estable)."""
    return sorted(items, key=lambda x: relevance(query, title(x)))
