"""Orden de los resultados de búsqueda por parecido con lo buscado."""

import unittest
from types import SimpleNamespace

from bot.services.japanpaw.ranking import ALL_WORDS, ELSEWHERE, EXACT, PHRASE, PREFIX, SUBSTRING, rank, relevance


def titles(*names):
    return [SimpleNamespace(title=n) for n in names]


class TestRanking(unittest.TestCase):
    def test_shiki_exact_beats_newer_partial_matches(self):
        # orden de la web (por fecha): el «Shiki» de verdad salía el décimo
        found = titles("Romeria Senki: … Guntai Soshiki Shita", "Zashiki Warashi no Tatami-chan", "Yuyushiki",
                       "Souryo to Majiwaru Shikiyoku no Yoru ni…", "Subarashiki Kono Sekai", "Shikioriori",
                       "Shiki", "Kawaii dake ja Nai Shikimori-san", "Inuyashiki", "Un anime que lo cita en la ficha")
        self.assertEqual(rank("Shiki", found)[0].title, "Shiki")

    def test_levels(self):
        self.assertEqual(relevance("shiki", "Shiki"), EXACT)
        self.assertEqual(relevance("Kimetsu no Yaiba", "Kimetsu no Yaiba: Yuukaku-hen"), PREFIX)
        self.assertEqual(relevance("Frieren", "Sousou no Frieren"), PHRASE)
        self.assertEqual(relevance("yaiba kimetsu", "Kimetsu no Yaiba"), ALL_WORDS)
        self.assertEqual(relevance("Shiki", "Yuyushiki"), SUBSTRING)
        self.assertEqual(relevance("Shiki", "Bocchi the Rock!"), ELSEWHERE)

    def test_ignores_case_accents_and_punctuation(self):
        self.assertEqual(relevance("dan da dan", "Dan Da Dan"), EXACT)
        self.assertEqual(relevance("pokemon", "Pokémon"), EXACT)
        self.assertEqual(relevance("100 man", "100-man no Inochi no Ue ni Ore wa Tatte Iru"), PREFIX)

    def test_ties_keep_site_order(self):
        found = titles("Monster Strike", "Monster Musume")
        self.assertEqual([x.title for x in rank("Monster", found)], ["Monster Strike", "Monster Musume"])
