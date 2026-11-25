"""Cliente de la web de anime: búsqueda, posts, fichas, portadas y cómo se descargan las páginas."""

import unittest
import urllib.parse
from unittest import mock

import httpx

from bot.services import aliases
from bot.services.japanpaw import JapanpawClient, SearchResult
from bot.services.japanpaw.fetchers import BrowserFetcher, DirectFetcher, FallbackFetcher, Fetcher, FetchFailed
from bot.services.japanpaw.parsing import is_allowed_url, is_cover_url
from bot.services.netblock import NetBypass
from tests.test_services import fake_http

BASE = "https://japanpaw.com"
PASTE = "https://paste.japan-paw.net/?v=8128"
CERT_ERROR = "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed"
REAL_CLIENT = httpx.AsyncClient   # el de verdad (fake_http parchea httpx.AsyncClient)


class FakeSite(Fetcher):
    """La web simulada: `handler(url, want_json)` responde cada descarga."""

    def __init__(self, handler):
        self.handler = handler
        self.urls: list[str] = []

    async def fetch(self, url: str, want_json: bool = False):
        self.urls.append(url)
        return self.handler(url, want_json)


def search_term(url: str) -> str | None:
    return urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("search", [None])[0]


def hit(post_id: int, title: str, url: str = "", subtype: str = "post") -> dict:
    return {"id": post_id, "title": title, "url": url or f"{BASE}/p{post_id}", "subtype": subtype}


def client_for(handler) -> tuple[JapanpawClient, FakeSite]:
    site = FakeSite(handler)
    return JapanpawClient(BASE + "/", "ws://browser", fetcher=site), site


def search_site(results: dict[str, list[dict]]):
    """Web que solo responde búsquedas: {término: resultados} (un Exception, se lanza)."""
    def handler(url, want_json):
        found = results.get(search_term(url), [])
        if isinstance(found, Exception):
            raise found
        return found
    return handler


# ---------------------------------------------------------------- búsqueda
class SearchTest(unittest.IsolatedAsyncioTestCase):
    async def test_asks_wordpress_for_many_posts(self):
        client, site = client_for(search_site({}))
        self.assertEqual(await client.search("Shiki"), [])
        query = urllib.parse.parse_qs(urllib.parse.urlparse(site.urls[0]).query)
        self.assertTrue(site.urls[0].startswith(f"{BASE}/wp-json/wp/v2/search?"))
        self.assertEqual(query, {"search": ["Shiki"], "per_page": ["100"], "type": ["post"], "subtype": ["post"]})

    async def test_only_posts_of_the_site_best_match_first(self):
        client, _ = client_for(search_site({"Shiki": [
            hit(1, "Yuyushiki"),
            hit(2, "Página", subtype="page"),
            hit(3, "Shiki", url="https://otra-web.com/shiki"),
            hit(4, "Shiki &amp; Specials"),
            hit(5, "Shiki"),
            hit(6, "  "),
        ]}))
        self.assertEqual(await client.search("Shiki"), [
            SearchResult(5, "Shiki", f"{BASE}/p5"),
            SearchResult(4, "Shiki & Specials", f"{BASE}/p4"),
            SearchResult(1, "Yuyushiki", f"{BASE}/p1"),
            SearchResult(6, "Post 6", f"{BASE}/p6"),
        ])

    async def test_keeps_the_best_eight(self):
        client, _ = client_for(search_site({"Shiki": [hit(i, f"Otra cosa {i}") for i in range(20)]
                                            + [hit(99, "Shiki")]}))
        found = await client.search("Shiki")
        self.assertEqual(len(found), JapanpawClient.MAX_RESULTS)
        self.assertEqual(found[0].post_id, 99)

    async def test_repeated_titles_are_told_apart_by_id(self):
        client, _ = client_for(search_site({"Monster": [hit(1, "Monster"), hit(2, "Monster"), hit(3, "Monster 2")]}))
        self.assertEqual([r.title for r in await client.search("Monster")],
                         ["Monster (#1)", "Monster (#2)", "Monster 2"])


ANILIST = "https://graphql.anilist.co"


def anilist_media(romaji: str, english: str | None = None, synonyms=()) -> dict:
    return {"title": {"romaji": romaji, "english": english}, "synonyms": list(synonyms)}


class SearchWithAliasesTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        aliases._cache.clear()
        self.addCleanup(aliases._cache.clear)
        self.anilist_calls = 0

    def anilist(self, *media):
        def handler(request):
            assert str(request.url).startswith(ANILIST), request.url
            self.anilist_calls += 1
            return httpx.Response(200, json={"data": {"Page": {"media": list(media)}}})
        patch = fake_http(handler)
        patch.start()
        self.addCleanup(patch.stop)

    async def test_enough_direct_results_do_not_ask_anilist(self):
        self.anilist()
        client, site = client_for(search_site({"Monster": [hit(1, "Monster"), hit(2, "Monster X"), hit(3, "Monster Y")]}))
        found, alias = await client.search_with_aliases("Monster")
        self.assertEqual([r.post_id for r in found], [1, 2, 3])
        self.assertIsNone(alias)
        self.assertEqual(self.anilist_calls, 0)

    async def test_nothing_direct_found_by_the_other_name(self):
        self.anilist(anilist_media("Kimi ni Todoke", "From Me to You"))
        client, _ = client_for(search_site({
            "From Me to You": [hit(7, "Kimi ni Todoke: From Me to You"), hit(8, "Algo sin relación")],
        }))
        found, alias = await client.search_with_aliases("Kimi ni Todoke")
        self.assertEqual([r.post_id for r in found], [7])
        self.assertEqual(alias, "From Me to You")

    async def test_alias_only_mentioned_when_nothing_came_directly(self):
        self.anilist(anilist_media("Kimi ni Todoke", "From Me to You"))
        client, _ = client_for(search_site({
            "Kimi ni Todoke": [hit(1, "Kimi ni Todoke")],
            "From Me to You": [hit(1, "Kimi ni Todoke"), hit(2, "Kimi ni Todoke 2nd Season")],
        }))
        found, alias = await client.search_with_aliases("Kimi ni Todoke")
        self.assertEqual([r.post_id for r in found], [1, 2])   # los directos primero, sin repetir
        self.assertIsNone(alias)

    async def test_a_failing_alias_is_skipped(self):
        self.anilist(anilist_media("Shingeki no Kyojin", "Attack on Titan", ["AoT Titans"]))
        client, site = client_for(search_site({
            "Attack on Titan": RuntimeError("la web no responde"),
            "AoT Titans": [hit(5, "Shingeki no Kyojin Season 3")],
        }))
        with self.assertLogs("bot.services.japanpaw", "WARNING"):
            found, alias = await client.search_with_aliases("Shingeki no Kyojin")
        self.assertEqual([r.post_id for r in found], [5])
        self.assertEqual(alias, "AoT Titans")

    async def test_stops_when_there_are_enough(self):
        self.anilist(anilist_media("Dandadan", "Dan Da Dan", ["DDD Dandadan"]))
        client, site = client_for(search_site({
            "Dan Da Dan": [hit(i, f"Dandadan {i}") for i in range(10)],
        }))
        found, alias = await client.search_with_aliases("Dandadan")
        self.assertEqual(len(found), JapanpawClient.MAX_RESULTS)
        self.assertEqual(alias, "Dan Da Dan")
        self.assertNotIn("DDD Dandadan", [search_term(u) for u in site.urls])


# ------------------------------------------------------------------ posts
def posts_site(items):
    def handler(url, want_json):
        if isinstance(items, Exception):
            raise items
        return items
    return handler


class PostKindsTest(unittest.IsolatedAsyncioTestCase):
    async def test_categories_of_each_post_in_one_query(self):
        client, site = client_for(posts_site([
            {"id": "1", "class_list": ["post-1", "category-pelicula", "category-en-emision"]},
            {"id": 2, "class_list": None},
        ]))
        self.assertEqual(await client.post_kinds([1, 2]), {1: {"pelicula", "en-emision"}, 2: set()})
        self.assertEqual(site.urls, [f"{BASE}/wp-json/wp/v2/posts?include=1,2&per_page=2&_fields=id,class_list"])

    async def test_no_posts_no_query(self):
        client, site = client_for(posts_site([]))
        self.assertEqual(await client.post_kinds([]), {})
        self.assertEqual(site.urls, [])

    async def test_failure_gives_nothing(self):
        client, _ = client_for(posts_site(RuntimeError("caída")))
        with self.assertLogs("bot.services.japanpaw", "WARNING"):
            self.assertEqual(await client.post_kinds([1]), {})

    async def test_empty_answer(self):
        client, _ = client_for(posts_site(None))
        self.assertEqual(await client.post_kinds([1]), {})


FICHA = """
<table>
  <tr><td><img src="https://switchmodo.com/icon.png"></td></tr>
  <tr><td><img src="https://japanpaw.com/wp/Season.png"></td></tr>
  <tr><td><img src="https://otra-web.com/cover.jpg"></td></tr>
  <tr><td><img src="https://s4.anilist.co/file/anilistcdn/media/anime/cover/medium/bx1.jpg"></td></tr>
  <tr><td><img src="https://japanpaw.com/otra.jpg"></td></tr>
  <tr><td>solo una celda</td></tr>
  <tr><td>icono</td><td>Episodios</td><td>12 / 12</td></tr>
  <tr><td>Temporada</td><td>Otoño 2009</td></tr>
  <tr><td>Fecha de estreno</td><td>2009-10-09</td></tr>
  <tr><td>Géneros</td><td>Drama, Terror</td></tr>
  <tr><td>Especificaciones del vídeo</td><td>BluRay 1080p</td></tr>
  <tr><td>Otro dato</td><td>no cuenta</td></tr>
  <tr><td><a class="DownloadV1" href="%s">Descargar</a></td></tr>
  <tr><td>Un pueblo aislado.<br>Visita Japan-Paw para más.<br>Mueren sus vecinos. (Escrito por Alguien)</td></tr>
</table>
""" % PASTE


class DetailsTest(unittest.IsolatedAsyncioTestCase):
    async def details_of(self, content: str):
        client, _ = client_for(posts_site([{"id": 1, "content": {"rendered": content}}]))
        return (await client.details([1]))[1]

    async def test_reads_the_ficha(self):
        d = await self.details_of(FICHA)
        self.assertEqual(d.cover_url, "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx1.jpg")
        self.assertEqual((d.episodes, d.season, d.premiere, d.genres, d.video),
                         ("12 / 12", "Otoño 2009", "2009-10-09", "Drama, Terror", "BluRay 1080p"))
        self.assertEqual(d.synopsis, "Un pueblo aislado. Mueren sus vecinos.")

    async def test_synopsis_plan_b_first_long_paragraph(self):
        long = "Una historia muy larga. " * 10
        cells = f"<td>{'x' * 100}</td><td>{'z' * 100}</td>"   # cada celda, corta; el párrafo entero, no
        d = await self.details_of(f"<p>Corto</p><p><table><tr>{cells}</tr></table></p><p>{long}</p>")
        self.assertEqual(d.synopsis, long.strip())

    async def test_download_button_outside_a_table_or_at_the_end(self):
        long = "y" * 160
        for content in (f'<a class="DownloadV1" href="{PASTE}">D</a><p>{long}</p>',
                        f'<table><tr><td><a class="DownloadV1" href="{PASTE}">D</a></td></tr></table><p>{long}</p>'):
            self.assertEqual((await self.details_of(content)).synopsis, long)

    async def test_empty_ficha(self):
        d = await self.details_of("")
        self.assertEqual((d.cover_url, d.synopsis, d.episodes), ("", "", ""))

    async def test_several_posts_in_one_query(self):
        client, site = client_for(posts_site([{"id": 1, "content": {"rendered": FICHA}}, {"id": 2}]))
        found = await client.details([1, 2])
        self.assertEqual(sorted(found), [1, 2])
        self.assertEqual(found[2].synopsis, "")
        self.assertEqual(site.urls, [f"{BASE}/wp-json/wp/v2/posts?include=1,2&per_page=2&_fields=id,content"])

    async def test_an_unreadable_ficha_is_skipped(self):
        client, _ = client_for(posts_site([{"content": {"rendered": FICHA}}, {"id": 2, "content": None}]))
        with self.assertLogs("bot.services.japanpaw", "WARNING"):
            self.assertEqual(list(await client.details([1, 2])), [2])

    async def test_no_posts_or_failure_gives_nothing(self):
        client, site = client_for(posts_site(RuntimeError("caída")))
        self.assertEqual(await client.details([]), {})
        self.assertEqual(site.urls, [])
        with self.assertLogs("bot.services.japanpaw", "WARNING"):
            self.assertEqual(await client.details([1]), {})


class PostByIdTest(unittest.IsolatedAsyncioTestCase):
    async def test_title_and_url(self):
        client, site = client_for(posts_site({"id": 3, "link": f"{BASE}/p3", "title": {"rendered": " A &amp; B "}}))
        self.assertEqual(await client.post_by_id(3), SearchResult(3, "A & B", f"{BASE}/p3"))
        self.assertEqual(site.urls, [f"{BASE}/wp-json/wp/v2/posts/3?_fields=id,link,title"])

    async def test_without_title(self):
        client, _ = client_for(posts_site({"id": 3, "link": f"{BASE}/p3", "title": None}))
        self.assertEqual(await client.post_by_id(3), SearchResult(3, "Post 3", f"{BASE}/p3"))

    async def test_link_outside_the_site(self):
        client, _ = client_for(posts_site({"id": 3, "link": "https://otra-web.com/p3"}))
        self.assertIsNone(await client.post_by_id(3))

    async def test_failure(self):
        client, _ = client_for(posts_site(RuntimeError("caída")))
        with self.assertLogs("bot.services.japanpaw", "ERROR"):
            self.assertIsNone(await client.post_by_id(3))


def post_page(post_id=5, classes="category-serie", title="Shiki BD 1080p [12 / 24] - Web", body="", ficha="24"):
    return f"""<html><head><title>{title}</title></head><body>
    <article class="post-{post_id} post {classes}"><h1>Shiki</h1>
      <table><tr><td>Episodios</td><td>{ficha}</td></tr></table>{body}
    </article></body></html>"""


class GetPostTest(unittest.IsolatedAsyncioTestCase):
    async def get(self, page_html: str, title: str = "", post_id: int = 5):
        client, site = client_for(lambda url, want_json: page_html)
        post = await client.get_post(f"{BASE}/shiki", post_id, title)
        self.assertEqual(site.urls, [f"{BASE}/shiki"])
        return post

    async def test_reads_the_page(self):
        post = await self.get(post_page(body=f'<a class="DownloadV1" href="{PASTE}">D</a>'))
        self.assertEqual((post.post_id, post.title, post.url), (5, "Shiki", f"{BASE}/shiki"))
        self.assertEqual((post.paste_url, post.paste_id), (PASTE, "8128"))
        self.assertEqual(post.label, "BD 1080p [12/24]")
        self.assertEqual((post.airing, post.movie), (False, False))

    async def test_paste_link_without_the_button(self):
        post = await self.get(post_page(body=f'<a class="DownloadV1" href="https://otra.com">D</a><a href="{PASTE}">x</a>'))
        self.assertEqual(post.paste_id, "8128")

    async def test_no_paste_link(self):
        post = await self.get(post_page(body='<a href="https://otra.com">x</a>'))
        self.assertEqual((post.paste_url, post.paste_id), (None, None))

    async def test_movie_airing_and_unknown_episode_count(self):
        post = await self.get(post_page(classes="category-pelicula category-en-emision", title="Shiki Web 720p [3/??]"))
        self.assertEqual((post.airing, post.movie, post.label), (True, True, "Web 720p [3/??]"))

    async def test_post_in_a_div_instead_of_article(self):
        page = (f'<html><head><title>T</title></head><body><div class="hentry post-5 category-pelicula">'
                f'</div></body></html>')
        post = await self.get(page, title="Dado")
        self.assertEqual((post.title, post.movie, post.label), ("Dado", True, ""))

    async def test_without_post_nor_h1_uses_the_page_title(self):
        post = await self.get("<html><head><title>Solo el título</title></head><body></body></html>")
        self.assertEqual((post.title, post.airing, post.movie), ("Solo el título", False, False))

    async def test_without_any_title(self):
        self.assertEqual((await self.get("<p>nada</p>")).title, "")

    async def test_refuses_urls_outside_the_site(self):
        client, site = client_for(lambda url, want_json: "")
        with self.assertRaises(ValueError):
            await client.get_post("https://otra-web.com/x", 1)
        self.assertEqual(site.urls, [])


# --------------------------------------------------------------- portadas
COVER = "https://japanpaw.com/wp-content/cover.jpg"


class CoverBytesTest(unittest.IsolatedAsyncioTestCase):
    async def cover(self, handler, url=COVER):
        with fake_http(handler):
            client = JapanpawClient(BASE, "ws://browser", fetcher=FakeSite(None))
            try:
                return await client.cover_bytes(url)
            finally:
                await client.close()

    async def test_downloads_the_image(self):
        seen = []

        def handler(request):
            seen.append(request)
            return httpx.Response(200, content=b"jpg", headers={"content-type": "image/jpeg"})

        self.assertEqual(await self.cover(handler), b"jpg")
        self.assertIn("Mozilla", seen[0].headers["user-agent"])

    async def test_only_https_covers_of_known_hosts(self):
        def handler(request):
            raise AssertionError("no debería descargar nada")
        for url in ("", "http://japanpaw.com/c.jpg", "https://otra-web.com/c.jpg"):
            self.assertIsNone(await self.cover(handler, url), url)

    async def test_not_an_image_empty_or_error(self):
        answers = [httpx.Response(404), httpx.Response(200, text="<html>", headers={"content-type": "text/html"}),
                   httpx.Response(200, content=b"", headers={"content-type": "image/png"})]
        for answer in answers:
            with self.assertLogs("bot.services.japanpaw", "INFO"):
                self.assertIsNone(await self.cover(lambda request: answer))

    async def test_network_failure(self):
        def handler(request):
            raise httpx.ConnectError("sin red")
        with self.assertLogs("bot.services.japanpaw", "INFO"):
            self.assertIsNone(await self.cover(handler))


class ClientWithoutFetcherTest(unittest.IsolatedAsyncioTestCase):
    async def test_by_default_downloads_directly_with_one_shared_client(self):
        def handler(request):
            return httpx.Response(200, json=[hit(1, "Shiki")])

        with fake_http(handler):
            client = JapanpawClient(BASE, "ws://browser")
            self.assertEqual(await client.search("Shiki"), [SearchResult(1, "Shiki", f"{BASE}/p1")])
            self.assertIs(client.http, client.http)
            await client.close()
        self.assertTrue(client.http.is_closed)

    async def test_close_without_having_downloaded(self):
        client = JapanpawClient(BASE, "ws://browser", force_browser=True)
        self.assertIsInstance(client.fetcher, BrowserFetcher)
        await client.close()


# --------------------------------------------------------------- parsing
class UrlsTest(unittest.TestCase):
    def test_allowed_urls(self):
        self.assertTrue(is_allowed_url("https://japanpaw.com/x"))
        self.assertTrue(is_allowed_url("http://www.japan-paw.net/x"))
        self.assertFalse(is_allowed_url("https://notjapanpaw.com/x"))
        self.assertFalse(is_allowed_url("ftp://japanpaw.com/x"))
        self.assertFalse(is_allowed_url("http://[roto"))

    def test_cover_urls(self):
        self.assertTrue(is_cover_url("https://s4.anilist.co/c.jpg"))
        self.assertFalse(is_cover_url("http://s4.anilist.co/c.jpg"))


# -------------------------------------------------------------- fetchers
def response(status=200, text="ok", url="https://japanpaw.com/x", **kwargs):
    return httpx.Response(status, text=text, request=httpx.Request("GET", url), **kwargs)


class FakeProxy(NetBypass):
    """El proxy simulado: `answer(url)` responde (o lanza)."""

    def __init__(self, answer=None, proxy="socks5://tor:9050"):
        super().__init__(proxy)
        self.answer = answer
        self.urls: list[str] = []

    async def get_proxied(self, url):
        self.urls.append(url)
        return self.answer(url)


def direct(handler, bypass=None):
    """DirectFetcher con la red simulada por `handler`; devuelve (fetcher, peticiones)."""
    seen: list[httpx.Request] = []

    def record(request):
        seen.append(request)
        return handler(request)

    client = REAL_CLIENT(transport=httpx.MockTransport(record))
    return DirectFetcher(lambda: client, bypass), seen


def cert_error(request):
    raise httpx.ConnectError(CERT_ERROR, request=request)


def no_sleep():
    return mock.patch("bot.services.japanpaw.fetchers.asyncio.sleep", mock.AsyncMock())


class DirectFetcherTest(unittest.IsolatedAsyncioTestCase):
    async def test_text_or_json(self):
        f, _ = direct(lambda r: httpx.Response(200, text='{"a": 1}'))
        self.assertEqual(await f.fetch("https://japanpaw.com/x", want_json=True), {"a": 1})
        self.assertEqual(await f.fetch("https://japanpaw.com/x"), '{"a": 1}')

    async def test_retries_once_after_an_error(self):
        answers = [httpx.Response(500), httpx.Response(200, text="ok")]
        f, seen = direct(lambda r: answers.pop(0))
        with no_sleep() as sleep, self.assertLogs("bot.services.japanpaw", "WARNING"):
            self.assertEqual(await f.fetch("https://japanpaw.com/x"), "ok")
        self.assertEqual(len(seen), 2)
        sleep.assert_awaited_once_with(2)

    async def test_gives_up_after_two_errors(self):
        f, seen = direct(lambda r: httpx.Response(200, text="no es json"))
        with no_sleep(), self.assertLogs("bot.services.japanpaw", "WARNING"):
            with self.assertRaises(FetchFailed):
                await f.fetch("https://japanpaw.com/x", want_json=True)
        self.assertEqual(len(seen), 2)

    async def test_blocked_without_proxy_goes_to_the_browser(self):
        for page in (httpx.Response(429), httpx.Response(200, text="<title>Just a moment...</title>")):
            f, seen = direct(lambda r: page)
            with self.assertLogs("bot.services.japanpaw", "WARNING"), self.assertRaises(FetchFailed):
                await f.fetch("https://japanpaw.com/x")
            self.assertEqual(len(seen), 1)   # un bloqueo no se reintenta

    async def test_blocked_also_through_the_proxy(self):
        def tor_down(url):
            raise httpx.ConnectError("tor caído")

        for answer in (lambda url: response(403), lambda url: response(text="no json"), tor_down):
            proxy = FakeProxy(answer)
            f, _ = direct(lambda r: httpx.Response(403), proxy)
            with self.assertLogs("bot.services.japanpaw", "WARNING"), self.assertRaises(FetchFailed):
                await f.fetch("https://japanpaw.com/x", want_json=True)
            self.assertFalse(proxy.proxied("japanpaw.com"))

    async def test_a_proxied_host_goes_straight_through_the_proxy(self):
        proxy = FakeProxy(lambda url: response(403))
        with self.assertLogs("bot.services.netblock", "WARNING"):
            proxy.use_proxy("japanpaw.com")
        f, seen = direct(lambda r: httpx.Response(200), proxy)
        with self.assertLogs("bot.services.japanpaw", "WARNING"), self.assertRaises(FetchFailed):
            await f.fetch("https://japanpaw.com/x")
        self.assertEqual((len(seen), len(proxy.urls)), (0, 1))   # ni directo ni segundo intento

    async def test_fake_certificate_uses_another_ip_and_pins_it(self):
        def handler(request):
            if request.url.host in ("1.1.1.1", "8.8.8.8"):   # DNS cifrado
                return httpx.Response(200, json={"Answer": [{"type": 1, "data": "10.0.0.2"}]})
            if request.url.host == "10.0.0.2":
                return httpx.Response(200, text="desde otra IP")
            return cert_error(request)

        with fake_http(handler):
            f, seen = direct(handler)
            with self.assertLogs("bot.services.netblock", "WARNING"):
                self.assertEqual(await f.fetch("https://japanpaw.com/x"), "desde otra IP")
            self.assertEqual(await f.fetch("https://japanpaw.com/y"), "desde otra IP")
        self.assertEqual([(r.url.host, r.url.path) for r in seen],
                         [("japanpaw.com", "/x"), ("10.0.0.2", "/"), ("10.0.0.2", "/x"), ("10.0.0.2", "/y")])
        self.assertEqual(seen[-1].headers["host"], "japanpaw.com")

    async def test_fake_certificate_and_no_other_ip(self):
        def handler(request):
            if request.url.host in ("1.1.1.1", "8.8.8.8"):
                return httpx.Response(200, json={})
            return cert_error(request)

        with fake_http(handler):
            f, seen = direct(handler)
            with no_sleep(), self.assertLogs("bot.services", "WARNING"), self.assertRaises(FetchFailed):
                await f.fetch("https://japanpaw.com/x")
            proxy = FakeProxy(lambda url: response(text="por el proxy"))
            f, _ = direct(handler, proxy)
            with self.assertLogs("bot.services", "WARNING"):
                self.assertEqual(await f.fetch("https://japanpaw.com/x"), "por el proxy")
        self.assertTrue(proxy.proxied("japanpaw.com"))

    async def test_other_network_errors_are_not_a_block(self):
        def handler(request):
            raise httpx.ConnectError("sin red", request=request)

        f, seen = direct(handler, FakeProxy(lambda url: self.fail("no debería ir por el proxy")))
        with no_sleep(), self.assertLogs("bot.services.japanpaw", "WARNING"), self.assertRaises(FetchFailed):
            await f.fetch("https://japanpaw.com/x")
        self.assertEqual(len(seen), 2)


class FakePage:
    """Una pestaña del navegador que muestra el challenge `challenges` veces."""

    def __init__(self, challenges: int, html="<html>la ficha</html>"):
        self.challenges = challenges
        self.html = html
        self.waited = 0

    def content(self):
        return "<title>Just a moment...</title>" if self.waited < self.challenges else self.html

    def wait_for_timeout(self, ms):
        self.waited += 1


class BrowserFetcherTest(unittest.IsolatedAsyncioTestCase):
    async def fetch(self, rendered, want_json=False):
        f = BrowserFetcher("ws://browser")
        with mock.patch.object(f, "_render", return_value=rendered) as render:
            data = await f.fetch("https://japanpaw.com/x", want_json)
        render.assert_called_once_with("https://japanpaw.com/x")
        return data

    async def test_html_or_json_from_the_visible_text(self):
        self.assertEqual(await self.fetch(("<html>ok</html>", "ok")), "<html>ok</html>")
        self.assertEqual(await self.fetch(("<pre>[1]</pre>", "[1]"), want_json=True), [1])

    async def test_still_blocked(self):
        with self.assertRaises(FetchFailed):
            await self.fetch(("<title>Just a moment...</title>", ""))

    def test_waits_for_the_challenge_to_clear(self):
        from bot.services.japanpaw.fetchers import wait_challenge
        page = FakePage(challenges=3)
        wait_challenge(page)
        self.assertEqual(page.waited, 3)

    def test_gives_up_waiting_after_twenty_seconds(self):
        from bot.services.japanpaw.fetchers import wait_challenge
        page = FakePage(challenges=100)
        wait_challenge(page)
        self.assertEqual(page.waited, 20)


class FallbackFetcherTest(unittest.IsolatedAsyncioTestCase):
    async def test_first_that_works(self):
        def failing(url, want_json):
            raise FetchFailed("bloqueado")
        first, second = FakeSite(failing), FakeSite(lambda url, want_json: {"json": want_json})
        f = FallbackFetcher(first, second)
        self.assertEqual(await f.fetch("https://japanpaw.com/x", want_json=True), {"json": True})
        self.assertEqual((first.urls, second.urls), (["https://japanpaw.com/x"], ["https://japanpaw.com/x"]))

    async def test_all_fail(self):
        def failing(url, want_json):
            raise FetchFailed("el último error")
        with self.assertRaisesRegex(RuntimeError, "el último error"):
            await FallbackFetcher(FakeSite(failing), FakeSite(failing)).fetch("https://japanpaw.com/x")
        with self.assertRaisesRegex(RuntimeError, "no se pudo descargar https://japanpaw.com/x"):
            await FallbackFetcher().fetch("https://japanpaw.com/x")

    async def test_other_errors_are_not_hidden(self):
        def broken(url, want_json):
            raise KeyError("fallo de programación")
        with self.assertRaises(KeyError):
            await FallbackFetcher(FakeSite(broken), FakeSite(lambda u, j: "ok")).fetch("https://japanpaw.com/x")


if __name__ == "__main__":
    unittest.main()
