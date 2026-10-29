"""IMDb-reading and merging helpers for add_wikidata_to_imdb.py.

Imported by other scripts; this is not a command to run directly.
"""

import gzip
import io
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from handle_release_dates import choose_release, split_for_year

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ("title.ratings", "title.basics", "title.crew", "title.principals")


def now():
    return datetime.now(timezone.utc).isoformat()


def extract(source, ids, cache, snapshots=None):
    """Cache one complete source extract; never treat a partial scan as complete."""
    path = cache / f"{source}.json"
    if path.exists():
        saved = json.loads(path.read_text(encoding="utf-8"))
        if saved["requested_ids"] == sorted(ids):
            print(f"Reusing completed {source} extract", flush=True)
            return saved
    url = f"https://datasets.imdbws.com/{source}.tsv.gz"
    print(f"Scanning {source} from IMDb (large compressed file)...", flush=True)
    started = now()
    found = {}
    last_update = time.monotonic()
    request = Request(url, headers={"User-Agent": "DS3001-MovieRatingProject/0.2"})
    local = cache / f"{source}.tsv.gz"
    if not local.exists() and snapshots is not None:
        shared = snapshots / f"{source}.tsv.gz"
        if shared.exists():
            local = shared
    with (local.open("rb") if local.exists() else urlopen(request, timeout=120)) as response:
        last_modified = getattr(response, "headers", {}).get("Last-Modified")
        with gzip.GzipFile(fileobj=response) as compressed:
            with io.TextIOWrapper(compressed, encoding="utf-8") as text:
                # Check the first column before parsing: almost every row belongs
                # to an unrelated title, especially in the large principals file.
                headers = next(text).rstrip("\r\n").split("\t")
                for count, line in enumerate(text, 1):
                    imdb_id = line.partition("\t")[0]
                    if imdb_id in ids:
                        row = dict(zip(headers, line.rstrip("\r\n").split("\t")))
                        found.setdefault(imdb_id, []).append(row)
                    if time.monotonic() - last_update > 20:
                        print(f"  {source}: scanned {count:,} rows; matched {len(found)}/{len(ids)} IDs", flush=True)
                        last_update = time.monotonic()
                    # These three files have one row per movie. Principals does not.
                    if source != "title.principals" and len(found) == len(ids):
                        break
    saved = {"source_url": url, "started_at_utc": started,
             "completed_at_utc": now(), "source_last_modified": last_modified,
             "requested_ids": sorted(ids), "rows": found}
    temporary = path.with_suffix(".part")
    temporary.write_text(json.dumps(saved, indent=2), encoding="utf-8")
    temporary.replace(path)
    print(f"Finished {source}: {len(found)}/{len(ids)} IDs matched", flush=True)
    return saved


def known(value):
    return "" if value in (None, "\\N") else value


def items(value):
    return known(value).split(",") if known(value) else []


def merge_row(wiki, sources):
    ids = [s["value"] for s in json.loads(wiki["imdb_ids"])]
    if len(ids) != 1:
        raise ValueError(f"Review ambiguous IMDb IDs for {wiki['wikidata_id']}: {ids}")
    imdb_id = ids[0]
    row = {"wikidata_id": wiki["wikidata_id"], "imdb_id": imdb_id,
           "wikidata_title": wiki["title"]}
    for name in ("languages", "countries", "budgets", "release_dates"):
        row[f"wikidata_{name}"] = wiki[name]
    row.update(choose_release(json.loads(wiki["release_dates"])))
    row["wikidata_earliest_release_date"] = row["release_date"]
    row["release_date_source"] = "Wikidata P577"
    supplemental_year = row["release_year"]
    notes = []
    records = {}
    for source in SOURCES:
        records[source] = sources[source]["rows"].get(imdb_id, [])
        if not records[source]:
            notes.append(f"missing {source}")
        if source != "title.principals" and len(records[source]) > 1:
            raise ValueError(f"Duplicate {source} rows for {imdb_id}")
    basics = (records["title.basics"] or [{}])[0]
    rating = (records["title.ratings"] or [{}])[0]
    crew = (records["title.crew"] or [{}])[0]
    row.update({"imdb_title": known(basics.get("primaryTitle")),
                "imdb_title_type": known(basics.get("titleType")),
                "imdb_start_year": known(basics.get("startYear")),
                "runtime_minutes": known(basics.get("runtimeMinutes")),
                "genres": json.dumps(items(basics.get("genres"))),
                "director_ids": json.dumps(items(crew.get("directors"))),
                "imdb_rating": known(rating.get("averageRating")),
                "imdb_vote_count": known(rating.get("numVotes"))})
    principals = records["title.principals"]
    # IMDb principals includes other jobs; only actor/actress entries are cast.
    cast = sorted((r for r in principals if r["category"] in ("actor", "actress")),
                  key=lambda r: int(r["ordering"]))
    row["principal_cast_ids"] = json.dumps(list(dict.fromkeys(r["nconst"] for r in cast)))
    if row["imdb_title_type"] and row["imdb_title_type"] not in ("movie", "tvMovie"):
        notes.append("IMDb titleType is outside movie/tvMovie scope")
    # IMDb startYear defines the population and splits. Other dates only enrich it.
    imdb_year = row["imdb_start_year"]
    row["release_year"] = int(imdb_year) if imdb_year.isdigit() else ""
    row["release_year_source"] = "IMDb startYear" if row["release_year"] != "" else ""
    row["release_month_source"] = ""
    if supplemental_year != "" and supplemental_year == row["release_year"]:
        if row["release_month"] != "":
            row["release_month_source"] = "Wikidata P577"
    else:
        if supplemental_year != "" and row["release_year"] != "":
            notes.append("IMDb and supplemental release years differ; month withheld")
        row.update(release_date=imdb_year if row["release_year"] != "" else "",
                   release_precision="year" if row["release_year"] != "" else "",
                   release_month="", release_date_source=row["release_year_source"])
    row["planned_split"] = split_for_year(row["release_year"])
    row["merge_review"] = "; ".join(notes)
    return row
