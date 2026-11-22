"""Lo que se saca de la web: resultados de búsqueda, posts y fichas."""

from dataclasses import dataclass


@dataclass
class SearchResult:
    post_id: int
    title: str
    url: str


@dataclass
class PostInfo:
    post_id: int
    title: str
    url: str
    paste_url: str | None
    paste_id: str | None
    airing: bool
    label: str           # p. ej. "Web 1080p [21/24]" (puede ser "")
    movie: bool = False  # categoría "pelicula"


@dataclass
class Details:
    """Ficha para elegir: portada, sinopsis y datos básicos."""
    cover_url: str = ""
    synopsis: str = ""
    episodes: str = ""
    season: str = ""      # "Otoño 2009"
    premiere: str = ""    # "2009-10-09"
    genres: str = ""
    video: str = ""       # "BluRay 1080p"
