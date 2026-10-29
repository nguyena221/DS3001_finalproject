"""Add cached Wikidata details and IMDb cast/directors to the selected US sample."""
import csv
import json

from request_wikidata import cached_entities, statements
from imdb_merge_helpers import ROOT, SOURCES, extract, merge_row
from collect_data_imdb import download


def main():
    cache = ROOT / 'data/cache'
    snapshots = ROOT / 'data/raw/imdb'
    with (cache / 'candidates.csv').open(encoding='utf-8-sig', newline='') as handle:
        candidates = list(csv.DictReader(handle))
    ids = {row['tconst'] for row in candidates}
    registry = json.loads((cache / 'us_registry.json').read_text(encoding='utf-8'))
    matches = {imdb_id: set() for imdb_id in ids}
    for binding in registry['results']['bindings']:
        imdb_id = binding['imdb']['value']
        if imdb_id in matches:
            matches[imdb_id].add(binding['movie']['value'].rsplit('/', 1)[-1])
    qids = sorted({next(iter(values)) for values in matches.values() if len(values) == 1})
    entities = cached_entities(qids, cache / 'wikidata.sqlite', 'DS3001-MovieProject/0.5')
    for source in ('title.crew', 'title.principals'):
        if not (cache / f'{source}.json').exists():
            download(source, snapshots)
    sources = {source: extract(source, ids, cache, snapshots=snapshots) for source in SOURCES}
    merged = []
    for candidate in candidates:
        imdb_id = candidate['tconst']
        matching_ids = matches[imdb_id]
        qid = next(iter(matching_ids)) if len(matching_ids) == 1 else ''
        entity = entities.get(qid, {})
        wiki = {'wikidata_id': qid,
                'title': entity.get('labels', {}).get('en', {}).get('value', candidate['primaryTitle']),
                'imdb_ids': json.dumps([{'value': imdb_id}])}
        for name, prop in {'languages': 'P364', 'countries': 'P495', 'budgets': 'P2130', 'release_dates': 'P577'}.items():
            wiki[name] = json.dumps(statements(entity, prop))
        row = merge_row(wiki, sources)
        row['wikidata_match_status'] = 'matched' if qid else ('ambiguous' if matching_ids else 'unmatched')
        row['wikidata_matching_ids'] = json.dumps(sorted(matching_ids))
        if not qid:
            row['merge_review'] = (row['merge_review'] + '; Wikidata ' + row['wikidata_match_status']).strip('; ')
        merged.append(row)
    if not merged:
        raise SystemExit('No candidates. Run collect_data_imdb.py first.')
    output = cache / 'combined_movies.csv'
    temporary = output.with_suffix('.part')
    with temporary.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(merged[0]))
        writer.writeheader()
        writer.writerows(merged)
    temporary.replace(output)
    print(f'Combined {len(merged):,} candidates. Run filter_movies.py to update the working dataset.')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit('Stopped. Completed downloads and entity batches are saved in data/cache/.')
