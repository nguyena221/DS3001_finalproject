# Data access and reproduction

Data files stay local and are not committed. Teammates must obtain source data
under its applicable terms; this repository does not redistribute IMDb records.

## Sources and access

- [Official IMDb downloads](https://data.imdb.com/non-commercial-datasets/):
  title.basics, title.ratings, title.crew, and title.principals compressed TSVs.
- [IMDb use conditions](https://help.imdb.com/article/imdb/general-information/can-i-use-imdb-data-in-my-software/G5JTRESSHJBBHTGX)
- [Wikidata licensing](https://www.wikidata.org/wiki/Wikidata:Licensing): US
  country-of-origin confirmation plus optional language, dates, and budgets.

The current saved collection was acquired October 26, 2026, using the scripts
below. Download provenance files retain original URLs and acquisition details.
No API key is needed. See the main README for eligibility and use limitations.

## Recreate the local dataset

From the repository root with Python 3.10 or newer:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe src\collect_data_imdb.py
.\.venv\Scripts\python.exe src\add_wikidata_to_imdb.py
.\.venv\Scripts\python.exe src\filter_movies.py
```

Skip environment creation if it already exists. Fresh collection can take a while
due to file sizes and service rate limits; completed response batches are cached.

- raw/imdb/: original compressed files and download provenance.
- cache/: selected candidates, IMDb extracts, US links, and saved Wikidata responses.
- processed/movies.csv: the working dataset, one row per movie.
- processed/summary.json: counts, planned splits, and missing-value totals.
- processed/excluded_movies.csv: created only if eligibility checks exclude rows.

Current local dataset: 10,000 US-origin movies/TV movies, including US co-productions,
with IMDb release years 2016-2025. Seed 42 repeats selection for the same snapshots;
new downloads may change records and ratings. The code uses IMDb year for splits
and does not fill optional missing values or train models. The course notebook
and report templates still need completion.

Keep source records, merged datasets, and restricted outputs out of commits. Only
this README and empty folder placeholders are intended to be tracked in data/.

