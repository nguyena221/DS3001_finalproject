"""Collect a rated US-only IMDb sample and record the selection rules.

Downloads basics/ratings once; caches compressed files locally for future runs.
Only a bounded candidate pool is kept in memory. No third-party packages needed.
"""
import argparse
from collections import Counter
import csv
import gzip
import hashlib
import heapq
from collections import defaultdict
import json
import time
from urllib.request import Request, urlopen

from imdb_merge_helpers import ROOT, now
from request_wikidata import get_json
from urllib.parse import urlencode


def download(name, folder):
    path = folder / f"{name}.tsv.gz"
    if path.exists():
        print(f"Using saved {path.name}", flush=True)
        return path
    url = f"https://datasets.imdbws.com/{path.name}"
    temporary = path.with_suffix(".part")
    print(f"Downloading {path.name}...", flush=True)
    with urlopen(Request(url, headers={"User-Agent": "DS3001-MovieProject/0.3"}), timeout=120) as response:
        metadata = {"url": url, "started_at_utc": now(),
                    "last_modified": response.headers.get("Last-Modified")}
        size, last = 0, time.monotonic()
        with temporary.open("wb") as handle:
            while chunk := response.read(1024 * 1024):
                handle.write(chunk)
                size += len(chunk)
                if time.monotonic() - last > 20:
                    print(f"  Downloaded {size / 1024**2:.0f} MiB", flush=True)
                    last = time.monotonic()
    metadata.update(completed_at_utc=now(), bytes=size)
    temporary.replace(path)
    path.with_suffix(".provenance.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return path


def scan(path):
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        yield from csv.DictReader(handle, delimiter="\t", quoting=csv.QUOTE_NONE)


def priority(imdb_id, seed):
    return int(hashlib.sha256(f"{seed}:{imdb_id}".encode()).hexdigest(), 16)


def allocate_quotas(capacities, target):
    """Distribute a total across years, reallocating when a year has too few films."""
    quotas = {year: 0 for year in sorted(capacities)}
    remaining = min(target, sum(capacities.values()))
    while remaining:
        for year in quotas:
            if quotas[year] < capacities[year]:
                quotas[year] += 1
                remaining -= 1
                if not remaining:
                    break
    return quotas


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--target-total", type=int, default=10000, help="Total US movie target (default: 10000), balanced across available years")
    args = parser.parse_args()
    if not 1 <= args.target_total <= 50000:
        parser.error("Choose a total target between 1 and 50,000")
    folder = ROOT / "data/cache"
    folder.mkdir(parents=True, exist_ok=True)
    snapshots = ROOT / "data/raw/imdb"
    snapshots.mkdir(parents=True, exist_ok=True)
    basics_path = download("title.basics", snapshots)
    ratings_path = download("title.ratings", snapshots)
    registry = folder / "us_registry.json"
    if not registry.exists():
        query = ('PREFIX wd: <http://www.wikidata.org/entity/> PREFIX wdt: <http://www.wikidata.org/prop/direct/> '
                 'SELECT DISTINCT ?imdb ?movie WHERE { ?movie wdt:P495 wd:Q30; wdt:P345 ?imdb . '
                 'FILTER(STRSTARTS(?imdb, "tt")) }')
        (folder / "us_registry.sparql").write_text(query, encoding="utf-8")
        print("Looking up US-production IMDb links in Wikidata...", flush=True)
        result = get_json("https://query.wikidata.org/sparql?" + urlencode({"query": query, "format": "json"}), "DS3001-MovieProject/0.4")
        registry.write_text(json.dumps(result, indent=2), encoding="utf-8")
        (folder / "us_registry_metadata.json").write_text(json.dumps({"retrieved_at_utc": now(),
            "source": "https://query.wikidata.org/sparql", "country_property": "P495", "country_id": "Q30"}, indent=2), encoding="utf-8")
    result = json.loads(registry.read_text(encoding="utf-8"))
    links = defaultdict(set)
    for binding in result["results"]["bindings"]:
        links[binding["imdb"]["value"]].add(binding["movie"]["value"])
    # Ambiguous IDs cannot be country-verified without review; don't spend a
    # sample slot on a known ambiguity when other rated candidates are available.
    us_ids = {imdb_id for imdb_id, qids in links.items() if len(qids) == 1}
    print(f"US registry: {len(us_ids):,} distinct IMDb IDs", flush=True)
    # First collect all rated IDs (not rating values) to avoid favoring popular films.
    print("Reading rated IMDb IDs...", flush=True)
    rated = {r["tconst"] for r in scan(ratings_path)}
    counts, window_counts = Counter(), Counter()
    pools = {year: [] for year in range(2016, 2026)}
    available = Counter()
    print("Counting all title types and selecting rated movie/tvMovie candidates...", flush=True)
    last = time.monotonic()
    for count, row in enumerate(scan(basics_path), 1):
        kind, year = row["titleType"], row["startYear"]
        counts[kind] += 1
        if year.isdigit() and 2016 <= int(year) <= 2025:
            window_counts[kind] += 1
        if (kind in ("movie", "tvMovie") and year.isdigit() and int(year) in pools
                and row["tconst"] in rated and row["tconst"] in us_ids):
            available[int(year)] += 1
            pool = pools[int(year)]
            entry = (-priority(row["tconst"], args.seed), row["tconst"], row)
            limit = args.target_total
            if len(pool) < limit:
                heapq.heappush(pool, entry)
            elif entry > pool[0]:
                heapq.heapreplace(pool, entry)
        if time.monotonic() - last > 20:
            print(f"  Counted {count:,} titles...", flush=True)
            last = time.monotonic()
    quotas = allocate_quotas({year: len(pool) for year, pool in pools.items()}, args.target_total)
    selected = [entry[2] for year in pools for entry in sorted(pools[year], reverse=True)[:quotas[year]]]
    ids = {r["tconst"] for r in selected}
    rating_rows = {r["tconst"]: [r] for r in scan(ratings_path) if r["tconst"] in ids}
    for source, rows in (("title.basics", {r["tconst"]: [r] for r in selected}), ("title.ratings", rating_rows)):
        (folder / f"{source}.json").write_text(json.dumps({
            "requested_ids": sorted(ids), "source_url": f"https://datasets.imdbws.com/{source}.tsv.gz",
            "local_snapshot": str(snapshots / f"{source}.tsv.gz"), "extracted_at_utc": now(),
            "rows": rows}, indent=2), encoding="utf-8")
    summary = {"created_at_utc": now(), "seed": args.seed,
               "target_total": args.target_total,
               "all_title_type_counts": dict(sorted(counts.items())),
               "imdb_2016_2025_type_counts": dict(sorted(window_counts.items())),
               "selected": len(selected), "selected_by_imdb_year": quotas,
               "available_by_imdb_year": dict(sorted(available.items())),
               "us_only": True,
               "country_rule": "US (Q30) among Wikidata P495 countries; includes co-productions",
               "note": "IMDb year governs eligibility. Missing country cannot establish US origin. Reproducible hash sample within years for saved snapshots; Wikidata coverage limits the US population."}
    (folder / "selection_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    if not selected:
        raise SystemExit("No matching candidates; inspect source coverage before proceeding")
    with (folder / "candidates.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(selected[0]))
        writer.writeheader()
        writer.writerows(selected)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
