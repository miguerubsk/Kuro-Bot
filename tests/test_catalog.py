"""El catálogo de AniList (opciones, fichas, packs) y las sinopsis de TMDB, con la red simulada."""

import json
import unittest
from unittest import mock

import httpx

from tests.test_services import fake_http


def media(i, title, fmt="TV", status="FINISHED", rel=(), **extra):
    """Una entrada de AniList como las devuelve la API (rel: [(relación, id, formato)])."""
    return {"id": i, "title": {"romaji": title, "english": None, "native": None}, "format": fmt,
            "status": status, "episodes": 12, "startDate": {"year": 2020},
            "relations": {"edges": [{"relationType": r, "node": {"id": n, "format": f, "type": "ANIME"}}
                                    for r, n, f in rel]}, **extra}


def anilist(search=(), by_id=None, calls=None):
    """Un AniList falso: las búsquedas devuelven `search`; Media(id) sale de `by_id`."""
    by_id = by_id or {}

    def handler(request):
        variables = json.loads(request.content)["variables"]
        if calls is not None:
            calls.append(variables)
        if "id" in variables:
            return httpx.Response(200, json={"data": {"Media": by_id.get(variables["id"])}})
        return httpx.Response(200, json={"data": {"Page": {"media": list(search)}}})
    return fake_http(handler)


class OptionTest(unittest.TestCase):
    def option(self, **kw):
        from bot.services.catalog import Option
        base = dict(anilist_id=1, title="Kono Oto Tomare!", english="", format="TV", episodes=13,
                    year=2019, status="FINISHED")
        return Option(**{**base, **kw})

    def test_label(self):
        self.assertEqual(self.option().label(), "Kono Oto Tomare! · 2019 · TV · 13 caps.")
        self.assertEqual(self.option(status="RELEASING").label(), "Kono Oto Tomare! · 2019 · TV · en emisión")
        self.assertEqual(self.option(format="MOVIE", episodes=1, year=None).label(), "Kono Oto Tomare! · película")
        self.assertEqual(self.option(format="CM", episodes=None).label(), "Kono Oto Tomare! · 2019 · cm")

    def test_details_of_a_movie_without_synopsis(self):
        d = self.option(format="MOVIE", episodes=1, year=None).details()
        self.assertEqual((d.episodes, d.season, d.video, d.note), ("", "", "película", ""))

    def test_from_media_with_gaps(self):
        from bot.services.catalog import Option
        o = Option.from_media({"id": "5", "title": None, "relations": None, "season": "WINTER"})
        self.assertEqual((o.anilist_id, o.title, o.english, o.format, o.status), (5, "?", "", "", ""))
        self.assertEqual((o.year, o.cover_url, o.description, o.genres, o.native, o.season),
                         (None, "", "", [], "", "Invierno"))
        self.assertEqual(o.neighbours, [])

    def test_from_media_titles_and_relations(self):
        from bot.services.catalog import Option
        o = Option.from_media({
            "id": 9, "title": {"romaji": None, "english": "Sound!", "native": "響け"},
            "season": "SUMMER", "seasonYear": None, "startDate": None, "coverImage": None,
            "relations": {"edges": [
                {"relationType": "PREQUEL", "node": {"id": 1, "format": None, "type": "ANIME"}},
                {"relationType": "ADAPTATION", "node": {"id": 2, "format": "MANGA", "type": "MANGA"}},
                {"relationType": "SIDE_STORY", "node": {"id": 3, "format": "OVA", "type": "MANGA"}},
                {"relationType": "SIDE_STORY", "node": {"id": 4, "format": "MUSIC", "type": "ANIME"}},
                {"relationType": "PARENT", "node": None},
                {"relationType": "PARENT", "node": {"id": 6, "format": "TV", "type": "ANIME"}}]}})
        self.assertEqual((o.title, o.english, o.native, o.season), ("Sound!", "Sound!", "響け", "Verano"))
        self.assertEqual(o.neighbours, [("PREQUEL", 1, ""), ("PARENT", 6, "TV")])


class AniListCatalogTest(unittest.IsolatedAsyncioTestCase):
    async def test_options_keep_what_can_be_asked_for(self):
        from bot.services.catalog import AniListCatalog
        found = [media(1, "Serie"), media(2, "Canción", fmt="MUSIC"), media(3, "Futura", status="NOT_YET_RELEASED"),
                 media(4, "Película", fmt="MOVIE"), media(5, "OVA", fmt="OVA"), media(6, "Otra")]
        cat = AniListCatalog()
        calls = []
        with anilist(found, calls=calls):
            opts = await cat.options("serie", limit=3)
            self.assertEqual([o.title for o in opts], ["Serie", "Película", "OVA"])
            # las opciones de la búsqueda quedan a mano: no se vuelven a pedir
            self.assertEqual((await cat.option(4)).title, "Película")
        self.assertEqual(calls, [{"s": "serie"}])

    async def test_options_when_anilist_fails(self):
        from bot.services.catalog import AniListCatalog
        with fake_http(lambda request: httpx.Response(502)):
            self.assertIsNone(await AniListCatalog().options("serie"))

    async def test_options_with_nothing_found(self):
        from bot.services.catalog import AniListCatalog
        with fake_http(lambda request: httpx.Response(200, json={"data": {"Page": None}})):
            self.assertEqual(await AniListCatalog().options("serie"), [])

    async def test_option_by_id(self):
        from bot.services.catalog import AniListCatalog
        cat = AniListCatalog()
        calls = []
        with anilist(by_id={7: media(7, "Hibike")}, calls=calls):
            self.assertEqual((await cat.option(7)).title, "Hibike")
            self.assertEqual((await cat.option(7)).title, "Hibike")
            self.assertIsNone(await cat.option(8))
        self.assertEqual(calls, [{"id": 7}, {"id": 8}])

    async def test_option_when_anilist_fails(self):
        from bot.services.catalog import AniListCatalog
        with fake_http(lambda request: httpx.Response(500)):
            self.assertIsNone(await AniListCatalog().option(7))

    async def test_cache_is_emptied_when_it_grows(self):
        from bot.services import catalog
        cat = catalog.AniListCatalog()
        calls = []
        with anilist(by_id={i: media(i, f"A{i}") for i in range(503)}, calls=calls):
            for i in range(502):
                await cat.option(i)
            await cat.option(0)        # se vació al pasar de 500: hay que pedirla otra vez
        self.assertEqual(len(calls), 503)

    async def test_pack_over_the_network(self):
        """Desde la T2: hacia atrás hasta la T1, hacia delante por la película hasta la T3."""
        from bot.services.catalog import AniListCatalog
        entries = {1: media(1, "T1", rel=[("SEQUEL", 2, "TV")]),
                   2: media(2, "T2", rel=[("PREQUEL", 1, "TV"), ("SEQUEL", 3, "MOVIE"), ("SIDE_STORY", 9, "OVA")]),
                   3: media(3, "Película", fmt="MOVIE", rel=[("PREQUEL", 2, "TV"), ("SEQUEL", 4, "TV")]),
                   4: media(4, "T3", rel=[("PREQUEL", 3, "MOVIE")]),
                   9: media(9, "OVA", fmt="OVA", rel=[("PARENT", 2, "TV")])}
        with anilist(by_id=entries):
            pack = await AniListCatalog().pack(2)
        self.assertEqual([(o.title, o.tag) for o in pack],
                         [("T1", ""), ("T2", ""), ("OVA", "OVA"), ("Película", "🎬 Película"), ("T3", "")])

    async def test_pack_of_something_unknown(self):
        from bot.services.catalog import AniListCatalog
        with anilist():
            self.assertEqual(await AniListCatalog().pack(1), [])

    async def test_pack_stops_where_anilist_stops(self):
        from bot.services.catalog import AniListCatalog
        entries = {2: media(2, "T2", rel=[("PREQUEL", 1, "TV"), ("SEQUEL", 3, "TV"), ("SIDE_STORY", 9, "OVA")])}
        with anilist(by_id=entries):
            self.assertEqual([o.title for o in await AniListCatalog().pack(2)], ["T2"])

    async def test_pack_limits(self):
        """Como mucho MAX_SEASONS temporadas y MAX_EXTRAS extras (contando los que cuelgan aparte)."""
        from bot.services import catalog
        entries = {i: media(i, f"T{i}", rel=[("SEQUEL", i + 1, "TV")]) for i in range(1, 6)}
        entries[1]["relations"]["edges"] += [
            {"relationType": "SIDE_STORY", "node": {"id": 10 + n, "format": "OVA", "type": "ANIME"}}
            for n in range(4)]
        entries.update({10 + n: media(10 + n, f"OVA{n}", fmt="OVA") for n in range(4)})
        entries[6] = media(6, "Especial", fmt="SPECIAL")
        entries[5]["relations"]["edges"][0]["node"]["format"] = "SPECIAL"
        with anilist(by_id=entries), mock.patch.object(catalog, "MAX_SEASONS", 3), \
                mock.patch.object(catalog, "MAX_EXTRAS", 2):
            pack = await catalog.AniListCatalog().pack(1)
        self.assertEqual([o.title for o in pack], ["T1", "OVA0", "OVA1", "T2", "T3"])

    async def test_hops_are_limited(self):
        from bot.services import catalog
        entries = {i: media(i, f"T{i}", rel=[("PREQUEL", i - 1, "TV"), ("SEQUEL", i + 1, "TV")])
                   for i in range(1, 40)}
        with anilist(by_id=entries), mock.patch.object(catalog, "MAX_SEASONS", 99):
            pack = await catalog.AniListCatalog().pack(20)
        # 25 pasos hacia atrás (hasta el 1, que está a 19) y 25 hacia delante desde ahí
        self.assertEqual([o.anilist_id for o in pack], list(range(1, 27)))

    async def test_details_with_and_without_spanish(self):
        from bot.services.catalog import AniListCatalog, Option
        opt = Option(1, "Hibike", "Sound! Euphonium", "TV", 13, 2015, "FINISHED", description="In English.")
        self.assertEqual((await AniListCatalog().details([opt]))[1].synopsis, "In English.")
        tmdb = {"results": [{"original_language": "ja", "overview": "En español."}]}
        with fake_http(lambda request: httpx.Response(200, json=tmdb)):
            d = (await AniListCatalog("clave").details([opt]))[1]
        self.assertEqual((d.synopsis, d.note), ("En español.", ""))


class SpanishSynopsisTest(unittest.IsolatedAsyncioTestCase):
    def opt(self, **kw):
        from bot.services.catalog import Option
        base = dict(anilist_id=1, title="Hibike! Euphonium", english="Sound! Euphonium", format="TV",
                    episodes=13, year=2015, status="FINISHED", native="響け！ユーフォニアム")
        return Option(**{**base, **kw})

    async def test_tries_each_name_until_a_japanese_one_has_overview(self):
        from bot.services.catalog import SpanishSynopsis
        asked = []

        def handler(request):
            q = request.url.params["query"]
            asked.append((q, request.url.params["api_key"], request.url.params["language"]))
            if q == "Sound! Euphonium":
                return httpx.Response(200, json={"results": [{"original_language": "en", "overview": "No."},
                                                             {"original_language": "ja", "overview": "  "}]})
            return httpx.Response(200, json={"results": [{"original_language": "ja", "overview": " Kumiko. "}]})

        s = SpanishSynopsis("k" * 32)
        with fake_http(handler):
            self.assertEqual(await s.find(self.opt()), "Kumiko.")
            self.assertEqual(await s.find(self.opt()), "Kumiko.")      # de la caché
        self.assertEqual(asked, [("Sound! Euphonium", "k" * 32, "es-ES"), ("Hibike! Euphonium", "k" * 32, "es-ES")])

    async def test_nothing_found_is_remembered(self):
        from bot.services.catalog import SpanishSynopsis
        asked = []

        def handler(request):
            asked.append(request.url.params["query"])
            return httpx.Response(200, json={"results": None})

        s = SpanishSynopsis("k" * 32)
        with fake_http(handler):
            self.assertEqual(await s.find(self.opt(english="", native="Hibike! Euphonium")), "")
            self.assertEqual(await s.find(self.opt()), "")
        self.assertEqual(asked, ["Hibike! Euphonium"])     # sin repetir nombres ni volver a preguntar

    async def test_read_token_goes_in_the_header(self):
        from bot.services.catalog import SpanishSynopsis
        seen = []

        def handler(request):
            seen.append((request.headers.get("Authorization"), "api_key" in request.url.params))
            return httpx.Response(200, json={"results": [{"original_language": "ja", "overview": "Sí."}]})

        token = "eyJ" + "x" * 60
        with fake_http(handler):
            self.assertEqual(await SpanishSynopsis(token).find(self.opt()), "Sí.")
        self.assertEqual(seen, [(f"Bearer {token}", False)])

    async def test_errors_give_nothing_and_are_not_remembered(self):
        from bot.services.catalog import SpanishSynopsis
        s = SpanishSynopsis("k" * 32)
        with fake_http(lambda request: httpx.Response(401)):
            self.assertEqual(await s.find(self.opt()), "")
        with fake_http(lambda request: httpx.Response(200, text="no es JSON")):
            self.assertEqual(await s.find(self.opt()), "")
        ok = {"results": [{"original_language": "ja", "overview": "Ahora sí."}]}
        with fake_http(lambda request: httpx.Response(200, json=ok)):
            self.assertEqual(await s.find(self.opt()), "Ahora sí.")


if __name__ == "__main__":
    unittest.main()
