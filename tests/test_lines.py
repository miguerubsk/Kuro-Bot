"""Las frases de Kuro: que cada variante solo use lo que el código le pasa, y que no se repitan."""

import random
import re
import string
import unittest
from collections import Counter

from bot.persona import Persona
from bot.persona import lines as L

ALWAYS = {"voc", "Voc", "site", "example"}
# valores que el código pasa a cada clave (además de voc/Voc/site)
KEY_ARGS = {
    "help_user": {"limit"}, "help_track": {"limit"}, "deny_id": {"chat_id"}, "deny_keyword": {"chat_id"},
    "admin_added": {"who", "chat_id"}, "admin_add_already": {"chat_id"}, "chat_id": {"chat_id"},
    "searching": {"query"}, "not_found": {"query"}, "alias_hint": {"query", "alias"},
    "history_mine": {"count"}, "history_client_one": {"who", "count"}, "history_client_few": {"who", "count"},
    "history_client_many": {"who", "count"}, "history_client_waiting": {"who", "count"},
    "history_empty_client": {"who"}, "reading_post": {"title"}, "no_link": {"title"},
    "checking_library": {"title"}, "library_complete": {"title", "have"}, "library_movie": {"title", "have"},
    "library_busy": {"title"}, "library_partial": {"have", "available", "count", "ranges"},
    "bundle_reading": {"title"}, "bundle_all_have": {"title"},
    "bundle_sent": {"title", "items_html", "left", "limit"}, "bundle_skipped": {"items_html"},
    "bundle_rejected": {"title"}, "admin_bundle_request": {"who", "bundle"}, "already_pending": {"title"},
    "no_quota": {"limit", "when_html"}, "no_quota_when": {"date"}, "quota_left": {"left", "limit"},
    "sent_to_admin": {"title", "label", "left", "limit"}, "sending": {"title", "label"},
    "approved": {"title"}, "approved_boss": {"title"}, "queued": {"count", "ranges"},
    "queued_untracked": {"count", "ranges"}, "rejected": {"title"}, "nothing_new": {"title"},
    "already_downloading": {"title"}, "tech_failure": {"title"}, "airing": {"progress"},
    "ep_done": {"name", "ep", "n", "total"}, "ep_retry": {"name", "ep", "delay"},
    "ep_fallback": {"name", "ep"}, "ep_failed": {"name", "ep"}, "job_done_all": {"name", "done"},
    "job_done_partial": {"name", "done", "failed", "failed_ranges"}, "job_failed": {"name"},
    "movie_done": {"name"}, "movie_retry": {"name", "delay"}, "movie_failed": {"name"},
    "movie_already": {"title"}, "admin_request": {"who", "req_id"}, "admin_new_member": {"who", "chat_id"},
    "admin_ep_failed": {"name", "ep", "req_id", "who", "error"},
    "admin_movie_failed": {"name", "ep", "req_id", "who", "error"},
    "admin_job_done": {"req_id", "who", "name", "done", "failed", "failed_html"}, "admin_reset": {"n"},
    "already_decided": {"status"}, "lonely_clients": {"count", "who"}, "lonely_last_title": {"title"},
    "track_offer": {"title"}, "track_ep_done": {"name", "ep"}, "track_offer_full": {"title", "limit"}, "track_declined": {"title"},
    "track_sent": {"title", "when"}, "track_joined": {"title", "when"}, "track_active": {"title", "when"},
    "track_rejected": {"title"}, "track_failed": {"title"}, "track_ended": {"title"}, "track_stopped": {"title"},
    "track_stopped_by_boss": {"title"}, "track_gone": {"title"}, "track_list_head": {"count"},
    "track_list_limit": {"count", "limit"}, "track_admin_request": {"who", "title"},
    "track_admin_joined": {"who", "title"}, "track_admin_approved": {"title"}, "track_admin_rejected": {"title"},
    "track_admin_failed": {"title"}, "track_admin_ended": {"title"}, "track_admin_delete_failed": {"title"},
    "track_admin_cd_retired": {"n"},
    "lonely_back": {"days"}, "lonely_back_hurt": {"days"}, "lonely_back_drama": {"days"},
}
PLAIN_KEYS = {"not_authorized", "already_decided", "track_gone"}   # van en alertas: sin HTML


def fields(template: str) -> set[str]:
    return {f for _, f, _, _ in string.Formatter().parse(template) if f}


def args_for(key: str) -> set[str]:
    if re.fullmatch(r"lonely_\d+", key):
        return {"days"}
    return KEY_ARGS.get(key, set())


class TestLines(unittest.TestCase):
    def all_variants(self):
        for table in (L.LINES, L.NIGHT_LINES):
            for key, variants in table.items():
                for v in variants:
                    yield key, v

    def test_night_keys_exist(self):
        self.assertFalse(set(L.NIGHT_LINES) - set(L.LINES))
        self.assertFalse(L.ASIDE_KEYS - set(L.LINES))

    def test_only_known_fields(self):
        for key, v in self.all_variants():
            with self.subTest(key=key, line=v[:50]):
                self.assertLessEqual(fields(v), args_for(key) | ALWAYS)

    def test_html_tags_balanced_and_no_real_site(self):
        for key, v in self.all_variants():
            with self.subTest(key=key, line=v[:50]):
                for tag in ("b", "i", "code"):
                    self.assertEqual(v.count(f"<{tag}>"), v.count(f"</{tag}>"))
                self.assertNotRegex(v.lower(), r"japan[- ]?paw")
                if key in PLAIN_KEYS:
                    self.assertNotIn("<", v)

    def test_no_duplicates(self):
        for key, variants in L.LINES.items():
            dup = [v for v, n in Counter(variants + L.NIGHT_LINES.get(key, [])).items() if n > 1]
            self.assertFalse(dup, key)

    def test_lonely_levels_are_consecutive(self):
        levels = sorted(int(k.split("_")[1]) for k in L.LINES if re.fullmatch(r"lonely_\d+", k))
        self.assertEqual(levels, list(range(1, len(levels) + 1)))
        self.assertGreaterEqual(len(levels), 7)

    def test_formats(self):
        p = Persona(random.Random(1))
        for key in L.LINES:
            for _ in range(len(L.LINES[key])):
                p.say(key, 1, **{a: 7 if a in {"ep", "n", "total"} else "x" for a in args_for(key)})

    def test_examples_vary(self):
        p = Persona(random.Random(5))
        texts = {p.say("ask_name", 1) for _ in range(30)}
        self.assertNotIn("{example}", "".join(texts))
        used = {t for t in L.EXAMPLE_TITLES if any(t in x for x in texts)}
        self.assertGreater(len(used), 10)
        self.assertNotRegex("".join(L.LINES["ask_name"] + L.LINES["not_found"]), "Frieren")

    def test_contractions(self):
        p = Persona(random.Random(2))
        for _ in range(60):
            text = p.say("search_error", 1) + p.say("searching", 1, query="x") + p.say("not_found", 1, query="x")
            self.assertNotRegex(text, r"\b(?:[Dd]e|[Aa]) el\b")

    def test_recent_variants_are_avoided(self):
        p = Persona(random.Random(3))
        key = "searching"
        n = len(L.LINES[key])
        picks = [p._pick(key, night=False) for _ in range(200)]
        window = min(n // 2, Persona.MEMORY)
        for i in range(window, len(picks)):
            self.assertNotIn(picks[i], picks[i - window:i])


class TestStories(unittest.TestCase):
    def test_lore_and_battles_are_valid(self):
        stories = [("lore", x) for lv in L.LORE for x in lv] + [("battle", x) for x in L.BATTLES]
        for kind, v in stories:
            with self.subTest(line=v[:50]):
                self.assertLessEqual(fields(v), ALWAYS | ({"title"} if kind == "battle" else set()))
                self.assertNotIn("<i>", v)
                self.assertEqual(v.count("<b>"), v.count("</b>"))
                self.assertNotRegex(v.lower(), r"japan[- ]?paw")
        self.assertEqual(len(L.LORE), len(L.TRUST_STEPS))
        self.assertEqual(len(L.LORE), len(L.LORE_CHANCE))
        self.assertFalse(L.STORY_KEYS - set(L.LINES))

    def stories(self, p, to, n=400):
        return [t for t in (p.say("approved", to, title="x") for _ in range(n)) if "\n\n" in t]

    def test_strangers_hear_nothing_regulars_hear_more(self):
        p = Persona(random.Random(7))
        p.set_boss(1)
        trust = {2: 0, 3: 1, 4: 3}
        p.set_rapport(trust.get, lambda: ["Anime <X>"])
        self.assertFalse(self.stories(p, 2))
        some, many = self.stories(p, 3), self.stories(p, 4)
        self.assertTrue(some)
        self.assertGreater(len(many), len(some))
        deep = {x.split("{")[0][:30] for x in L.LORE[2]}
        self.assertFalse(any(d in t for t in some for d in deep))
        self.assertTrue(any(d in t for t in many for d in deep))

    def test_boss_gets_battles_with_real_titles(self):
        p = Persona(random.Random(8))
        p.set_boss(1)
        p.set_rapport(lambda _: 3, lambda: ["Anime <X>"])
        told = self.stories(p, 1)
        self.assertTrue(told)
        self.assertTrue(all("🍖" in t for t in told))
        self.assertTrue(any("Anime &lt;X&gt;" in t for t in told))
        p.set_rapport(lambda _: 3, lambda: [])
        self.assertTrue(all("{title}" not in t and "<b></b>" not in t for t in self.stories(p, 1)))

    def test_without_rapport_nothing_is_added(self):
        p = Persona(random.Random(9))
        self.assertFalse(self.stories(p, 3))
