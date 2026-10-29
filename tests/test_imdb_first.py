import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from collect_data_imdb import priority, allocate_quotas
from filter_movies import exclusion_reason


class ImdbFirstChecks(unittest.TestCase):
    def test_total_quota_reallocates_short_year_without_inventing_records(self):
        self.assertEqual(allocate_quotas({2016: 10, 2017: 1, 2018: 10}, 9), {2016: 4, 2017: 1, 2018: 4})
        self.assertEqual(allocate_quotas({2016: 2, 2017: 1}, 10), {2016: 2, 2017: 1})
    def test_sampling_reproducible_and_seeded(self):
        self.assertEqual(priority('tt123', 42), priority('tt123', 42))
        self.assertNotEqual(priority('tt123', 42), priority('tt123', 43))

    def test_dates_required_for_final_scope(self):
        row = {'imdb_title_type': 'tvMovie', 'imdb_rating': '6', 'planned_split': 'review'}
        self.assertIn('held for review', exclusion_reason(row))
        row['planned_split'] = 'outside_scope'
        self.assertIn('outside', exclusion_reason(row))
        row['planned_split'] = 'test'
        self.assertEqual(exclusion_reason(row), '')

    def test_us_scope_includes_coproductions_not_unknown_or_other_countries(self):
        import json
        row = {'imdb_title_type': 'movie', 'imdb_rating': '6', 'planned_split': 'train'}
        self.assertIn('unconfirmed', exclusion_reason(row, us_only=True))
        row['wikidata_countries'] = json.dumps([{'value': {'id': 'Q145'}}])
        self.assertIn('No US', exclusion_reason(row, us_only=True))
        row['wikidata_countries'] = json.dumps([{'value': {'id': 'Q145'}}, {'value': {'id': 'Q30'}}])
        self.assertEqual(exclusion_reason(row, us_only=True), '')


if __name__ == '__main__':
    unittest.main()
