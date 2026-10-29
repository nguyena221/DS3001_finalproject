"""Keep IMDb-matched movies; preserve excluded rows and reasons separately."""

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def exclusion_reason(row, us_only=False):
    if not row["imdb_title_type"]:
        return "No matching IMDb basics record"
    if row["imdb_title_type"] not in ("movie", "tvMovie"):
        return f"IMDb titleType is {row['imdb_title_type']}, outside movie/tvMovie scope"
    if not row["imdb_rating"]:
        return "No IMDb rating available for target"
    if row.get("planned_split") == "review":
        return "Release year unresolved; held for review, not model-ready"
    if row.get("planned_split") == "outside_scope":
        return "IMDb release year outside 2016–2025"
    if us_only:
        countries = json.loads(row.get("wikidata_countries", "[]"))
        if not countries:
            return "US origin unconfirmed: country is missing"
        if not any(s.get("value", {}).get("id") == "Q30" for s in countries):
            return "No US country of origin recorded"
    return ""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/cache/combined_movies.csv")
    args = parser.parse_args()
    with args.input.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        rows = list(reader)
    kept, excluded = [], []
    output_folder = ROOT / "data/processed"
    output_folder.mkdir(parents=True, exist_ok=True)
    if not rows:
        parser.error("Input has no candidate rows; run collection and enrichment first")
    for row in rows:
        reason = exclusion_reason(row, us_only=True)
        if reason:
            excluded.append({**row, "exclusion_reason": reason})
        else:
            kept.append(row)
    for label, records, columns in (
        ("eligible", kept, fields),
        ("excluded", excluded, fields + ["exclusion_reason"]),
    ):
        output = output_folder / ("movies.csv" if label == "eligible" else "excluded_movies.csv")
        if label == "excluded" and not records:
            output.unlink(missing_ok=True)
            continue
        temporary = output.with_suffix(".part")
        with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(records)
        temporary.replace(output)
        print(f"{label}: {len(records)} movies -> {output}")
    features = {"Rating": "imdb_rating", "Year": "release_year", "Runtime": "runtime_minutes",
                "Genre": "genres", "Director": "director_ids", "Principal cast": "principal_cast_ids",
                "Language": "wikidata_languages", "Country": "wikidata_countries",
                "Release month": "release_month", "Budget": "wikidata_budgets"}
    summary = {"eligible_movies": len(kept), "excluded_movies": len(excluded), "us_only": True,
               "splits": dict(Counter(r["planned_split"] for r in kept)),
               "missing_counts": {name: sum(r.get(key, "").strip() in ("", "[]", "null", "\\N") for r in kept)
                                  for name, key in features.items()}}
    summary_path = output_folder / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
