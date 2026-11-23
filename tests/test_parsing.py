"""Lectura de la página de un post: sobre todo, saber si está en emisión."""

import unittest

from bot.services.japanpaw.parsing import parse_post_html

PASTE = '<a class="DownloadV1" href="https://paste.japan-paw.net/?v=8128">Descargar</a>'


def page(post_id: int, categories: str, episodes: str, related: str = "") -> str:
    return f"""<html><head><title>X Web 1080p - Japan-Paw!</title></head><body>
    <article class="post-{post_id} post hentry {categories}"><h1>X</h1>
      <table><tr><td>Episodios</td><td>{episodes}</td></tr><tr><td>{PASTE}</td></tr></table>
    </article>{related}</body></html>"""


class TestAiring(unittest.TestCase):
    def test_category(self):
        self.assertTrue(parse_post_html(page(1, "category-serie category-en-emision", "12"), 1, "u").airing)

    def test_ficha_says_airing_without_the_category(self):
        # la web a veces no pone la categoría, pero la ficha sí dice «En emisión»
        post = parse_post_html(page(41584, "category-serie category-web", "En emisión"), 41584, "u")
        self.assertTrue(post.airing)
        self.assertEqual(post.paste_url, "https://paste.japan-paw.net/?v=8128")

    def test_finished(self):
        self.assertFalse(parse_post_html(page(2, "category-serie", "24"), 2, "u").airing)

    def test_related_posts_do_not_count(self):
        related = ('<article class="post-9 post category-en-emision"><table><tr><td>Episodios</td>'
                   '<td>En emisión</td></tr></table></article>')
        self.assertFalse(parse_post_html(page(2, "category-serie", "24", related), 2, "u").airing)
