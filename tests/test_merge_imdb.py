"""Synthetic checks only: no IMDb records or network requests."""
import json
import gzip
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from imdb_merge_helpers import SOURCES, extract, merge_row
from filter_movies import exclusion_reason
from request_wikidata import cached_entities


class MergeChecks(unittest.TestCase):
    def setUp(self):
        self.wiki = {"wikidata_id": "Q_TEST", "title": "Synthetic",
                     "imdb_ids": json.dumps([{"value": "tt_TEST"}]),
                     "languages": "[]", "countries": "[]", "budgets": "[]",
                     "release_dates": json.dumps([{"value": {
                         "time": "+2024-00-00T00:00:00Z", "precision": 9,
                         "calendarmodel": "http://www.wikidata.org/entity/Q1985727"}}])}
        self.sources = {s: {"rows": {}} for s in SOURCES}

    def test_missing_matches_preserved_and_date_not_invented(self):
        row = merge_row(self.wiki, self.sources)
        self.assertEqual(row["imdb_rating"], "")
        self.assertEqual(row["release_month"], "")
        self.assertEqual(row["planned_split"], "review")
        self.assertIn("missing title.ratings", row["merge_review"])

    def test_source_authority_cast_order_and_nulls(self):
        self.sources["title.basics"]["rows"]["tt_TEST"] = [{
            "primaryTitle": "IMDb synthetic", "startYear": "2025",
            "titleType": "movie", "runtimeMinutes": "\\N", "genres": "Drama,Comedy"}]
        self.sources["title.principals"]["rows"]["tt_TEST"] = [
            {"category": "actor", "ordering": "3", "nconst": "nm_B"},
            {"category": "director", "ordering": "1", "nconst": "nm_D"},
            {"category": "actress", "ordering": "2", "nconst": "nm_A"}]
        row = merge_row(self.wiki, self.sources)
        self.assertEqual(json.loads(row["principal_cast_ids"]), ["nm_A", "nm_B"])
        self.assertEqual(row["runtime_minutes"], "")
        self.assertEqual(json.loads(row["genres"]), ["Drama", "Comedy"])
        self.assertEqual(row["release_year"], 2025)
        self.assertEqual(row["release_month"], "")
        self.assertEqual(row["planned_split"], "test")
        self.assertIn("release years differ", row["merge_review"])

    def test_ambiguous_ids_rejected(self):
        self.wiki["imdb_ids"] = '[{"value": "a"}, {"value": "b"}]'
        with self.assertRaises(ValueError):
            merge_row(self.wiki, self.sources)

    def test_tv_movie_allowed_but_video_excluded(self):
        row = {"imdb_title_type": "tvMovie", "imdb_rating": "6.0"}
        self.assertEqual(exclusion_reason(row), "")
        row["imdb_title_type"] = "video"
        self.assertTrue(exclusion_reason(row))
        row["imdb_title_type"] = "movie"
        row["imdb_rating"] = ""
        self.assertTrue(exclusion_reason(row))

    def test_entity_cache_reuses_saved_response_without_network(self):
        entity = {'id': 'Q_TEST', 'claims': {}}
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder) / 'wikidata.sqlite'
            with patch('request_wikidata.fetch_entities', return_value={'Q_TEST': entity}) as fetch:
                first = cached_entities(['Q_TEST'], database, 'test')
                second = cached_entities(['Q_TEST'], database, 'test')
                self.assertEqual(first, second)
                self.assertEqual(second['Q_TEST'], entity)
                self.assertEqual(fetch.call_count, 1)

    def test_missing_wikidata_dates_do_not_remove_imdb_year(self):
        self.wiki["release_dates"] = "[]"
        self.sources["title.basics"]["rows"]["tt_TEST"] = [{"startYear": "2024", "titleType": "movie"}]
        row = merge_row(self.wiki, self.sources)
        self.assertEqual(row["release_year"], 2024)
        self.assertEqual(row["planned_split"], "validation")
        self.assertEqual(row["release_month"], "")

    def test_matching_year_keeps_month(self):
        self.wiki["release_dates"] = json.dumps([{"value": {"time": "+2024-07-03T00:00:00Z", "precision": 11,
                      "calendarmodel": "http://www.wikidata.org/entity/Q1985727"}}])
        self.sources["title.basics"]["rows"]["tt_TEST"] = [{"startYear": "2024", "titleType": "movie"}]
        row = merge_row(self.wiki, self.sources)
        self.assertEqual(row["release_month"], 7)
        self.assertEqual(row["release_month_source"], "Wikidata P577")

    def test_stream_retains_all_principal_rows_and_reuses_cache(self):
        payload = ('tconst\tordering\tnconst\tcategory\n'
                   'tt_OTHER\t1\tnm_SKIP\tactor\n'
                   'tt_TEST\t1\tnm_A\tactor\n'
                   'tt_TEST\t2\tnm_B\tactress\n')
        response = io.BytesIO(gzip.compress(payload.encode()))
        response.headers = {}
        with tempfile.TemporaryDirectory() as folder:
            with patch('imdb_merge_helpers.urlopen', return_value=response) as network:
                first = extract('title.principals', {'tt_TEST'}, Path(folder))
                second = extract('title.principals', {'tt_TEST'}, Path(folder))
                self.assertEqual(len(first['rows']['tt_TEST']), 2)
                self.assertEqual(first, second)
                self.assertEqual(network.call_count, 1)


if __name__ == "__main__":
    unittest.main()
