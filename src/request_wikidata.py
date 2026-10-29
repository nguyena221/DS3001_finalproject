"""Wikidata request, retry, and statement helpers; imported, not run directly."""

import json
import sqlite3
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

NEXT_QUERY_AT = 0.0
NEXT_API_AT = 0.0


def get_json(url, user_agent):
    """Make sequential requests; retry temporary server failures politely."""
    global NEXT_QUERY_AT, NEXT_API_AT
    is_query = url.startswith("https://query.wikidata.org/")
    is_api = url.startswith("https://www.wikidata.org/w/api.php")
    for attempt in range(3):
        try:
            if is_query:
                remaining = NEXT_QUERY_AT - time.monotonic()
                if remaining > 0:
                    print(f"  Waiting {remaining:.0f}s to respect the query rate limit...", flush=True)
                    time.sleep(remaining)
                NEXT_QUERY_AT = time.monotonic() + 65
            if is_api:
                remaining = NEXT_API_AT - time.monotonic()
                if remaining > 0:
                    time.sleep(remaining)
                NEXT_API_AT = time.monotonic() + 7
            request = Request(url, headers={"User-Agent": user_agent,
                                           "Accept": "application/json"})
            with urlopen(request, timeout=90) as response:
                result = json.load(response)
            time.sleep(1)
            return result
        except HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise
            wait = error.headers.get("Retry-After", "")
            retry_seconds = 0
            if wait.isdigit():
                retry_seconds = int(wait)
            elif wait:
                try:
                    retry_seconds = max(0, (parsedate_to_datetime(wait) - datetime.now(timezone.utc)).total_seconds())
                except (TypeError, ValueError, OverflowError):
                    pass
            delay = max(65 if error.code == 429 else 5 * (attempt + 1), retry_seconds)
            print(f"  HTTP {error.code}: waiting {delay:.0f}s before retry {attempt + 2}/3...", flush=True)
            time.sleep(delay)
        except (URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))


def fetch_entities(ids, user_agent):
    entities = {}
    for offset in range(0, len(ids), 50):
        params = urlencode({"action": "wbgetentities", "format": "json",
                            "ids": "|".join(ids[offset:offset + 50]),
                            "props": "labels|claims", "languages": "en"})
        result = get_json("https://www.wikidata.org/w/api.php?" + params, user_agent)
        entities.update(result["entities"])
    return entities


def statements(entity, property_id):
    """Keep all non-deprecated, known values; preserve precision and units."""
    values = []
    for claim in entity.get("claims", {}).get(property_id, []):
        snak = claim.get("mainsnak", {})
        if claim.get("rank") == "deprecated" or snak.get("snaktype") != "value":
            continue
        values.append({"value": snak["datavalue"]["value"],
                       "rank": claim.get("rank"),
                       "qualifiers": claim.get("qualifiers", {})})
    return values


def cached_entities(ids, database_path, user_agent):
    """Keep all saved entity responses in one local SQLite file, not thousands of files."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    database = sqlite3.connect(database_path)
    try:
        database.execute("CREATE TABLE IF NOT EXISTS entities (qid TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        entities, missing = {}, []
        for qid in ids:
            saved = database.execute("SELECT payload FROM entities WHERE qid=?", (qid,)).fetchone()
            if saved:
                entities[qid] = json.loads(saved[0])
            else:
                missing.append(qid)
        for offset in range(0, len(missing), 50):
            print(f"Fetching Wikidata details {offset + 1}-{min(offset + 50, len(missing))}/{len(missing)}...", flush=True)
            batch = fetch_entities(missing[offset:offset + 50], user_agent)
            for qid, entity in batch.items():
                database.execute("INSERT OR REPLACE INTO entities VALUES (?, ?)", (qid, json.dumps(entity)))
            database.commit()
            entities.update(batch)
        return entities
    finally:
        database.close()
