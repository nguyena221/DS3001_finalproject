# Movie rating prediction

## Course repository

- **Team:** Team 15 (member names still need to be filled in).
- **Repository:** https://github.com/nguyena221/DS3001_finalproject
- **notebook.ipynb:** the course analysis notebook template; still needs analysis
  and project-information placeholders completed.
- **final_report.docx:** the required report template, retained unchanged with
  its original filename; it has not been filled in yet.
- **data/README.md:** source access and reproduction instructions.

The collection scripts support the course notebook. Before submission, the
completed notebook must run from start to finish and reproduce the report results.

We're predicting IMDb ratings for **10,000 US-origin movies and TV movies with
IMDb release years 2016-2025**, including US co-productions. Collection works;
we have not filled missing values, finalized features, or trained models yet.

## Start here

**Open `data/processed/movies.csv` for the current dataset.**
`data/processed/summary.json` shows counts, planned splits, and missing fields.
Both files stay local and are ignored by Git.

The current split labels are **8,184 training / 1,008 validation / 808 testing**.
These labels organize the records; no model has been trained or evaluated.

## Folder and file guide

| Folder | What belongs here |
|---|---|
| src/ | Six Python files that collect, combine, and check the data. |
| tests/ | Small checks using made-up records, not downloaded data. |
| data/processed/ | The dataset and its summary: the files we actually inspect. |
| data/raw/imdb/ | Original compressed IMDb downloads, retained to avoid downloading again. |
| data/cache/ | Automatic saved results used to resume or rebuild the dataset. Usually leave these alone. |

### Top-level files

- **README.md:** this guide, project decisions, results, and a short history.
- **.gitignore:** prevents local data, caches, environments, and secrets from entering Git.
- **requirements.txt:** optional packages for later exploration and modeling.
  Current collection uses only Python's standard library.

### src/: every file has a current purpose

| File | Plain-English explanation |
|---|---|
| collect_data_imdb.py | Reads IMDb basics/ratings, confirms US-origin IDs through Wikidata, and selects the sample. Defaults to 10,000 US-only records. |
| add_wikidata_to_imdb.py | Adds language, country, dates, budget, directors, and principal cast to those selected movies. Saves an intermediate table in the cache. |
| filter_movies.py | Applies the agreed rules and writes movies.csv and summary.json. Writes excluded_movies.csv only if records were excluded. It does not fill missing values or train models. |
| imdb_merge_helpers.py | Shared functions used by the scripts to read IMDb files and combine movie records. Uses IMDb's year for eligibility and splits. Do not run directly. |
| request_wikidata.py | Requests Wikidata data, respects service limits, and stores/reuses responses in one cache file. Do not run directly. |
| handle_release_dates.py | Interprets optional Wikidata dates without inventing missing months/days, and assigns split labels from the IMDb year. Do not run directly. |

### data/processed/: the useful outputs

| File | Purpose |
|---|---|
| movies.csv | The current 10,000-movie table, one row per movie. List-valued cells contain JSON, such as several genres or actor IDs. |
| summary.json | Eligible/excluded counts, year-group totals, and missing-value counts. |
| excluded_movies.csv (only when needed) | Excluded or held records with a reason. It is absent now because all 10,000 selected records passed. |
| .gitkeep | Empty placeholder so Git retains the processed folder without uploading data. |

### data/raw/imdb/: source downloads

- **title.basics.tsv.gz:** titles, types, IMDb years, runtime, and genres.
- **title.ratings.tsv.gz:** IMDb ratings and vote counts.
- **title.crew.tsv.gz:** director/writer IDs.
- **title.principals.tsv.gz:** principal cast and crew, not the complete cast.
- **Each matching .tsv.provenance.json:** source URL and original download details.
- **data/raw/.gitkeep:** empty placeholder for the raw folder.

These are the large source files. Keeping them makes future rebuilds faster;
deleting them would force downloads again. They never go to GitHub.

### data/cache/: generated files, not extra datasets to choose between

| File | Purpose |
|---|---|
| candidates.csv | IMDb records selected before the final checks. |
| selection_summary.json | Seed, requested size, available records, year quotas, and actual IMDb title-type counts. |
| us_registry.json | Saved Wikidata links between US-origin records and IMDb IDs. |
| us_registry.sparql | The query used to get those links. |
| us_registry_metadata.json (when present) | Query endpoint, country property, and retrieval time. |
| title.basics.json | Original basics rows matching the selected IDs. |
| title.ratings.json | Original rating rows matching those IDs. |
| title.crew.json | Matching director/writer rows. |
| title.principals.json | Matching principal cast/crew rows. |
| wikidata.sqlite | A single saved-response database replacing 10,000 separate entity JSON files. The scripts read it automatically; you do not need to use SQL. |
| combined_movies.csv | Intermediate merged table before filtering. Open processed/movies.csv for normal analysis instead. |

Temporary .part files are incomplete writes/downloads. The scripts do not treat
them as completed data. Python may also generate __pycache__/ folders; those,
.venv/, and Git's own .git/ folder are not project files to edit.

### tests/: code checks, not model evaluation

- **test_imdb_first.py:** selection priorities, year quotas, and US eligibility.
- **test_merge_imdb.py:** missing records, cast ordering, source matching, optional
  months, and reuse of the saved-response cache.

## Run the workflow

Python 3.10 or newer. Create the environment only if it does not already exist:

```powershell
python -m venv .venv
```

Then run these three scripts in order. No extra flags are needed:

```powershell
.\.venv\Scripts\python.exe src\collect_data_imdb.py
.\.venv\Scripts\python.exe src\add_wikidata_to_imdb.py
.\.venv\Scripts\python.exe src\filter_movies.py
```

To request a different size, use `collect_data_imdb.py --target-total NUMBER`.
Slots are balanced across years, reallocating if a year has too few qualifying
records. Our saved sources have only 808 qualifying 2025 titles and 1,008 from
2024, so the other years supply 1,023 each. Selection uses a fixed seed, not
rating value or popularity. Reproduction depends on the saved source snapshots;
live data can change. Fresh Wikidata collection can take a while because of rate
limits. Completed response batches are saved; cached rebuilds need no new lookups.

Run the code checks with:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

## Data sources and rules

- **IMDb:** rating target, vote count, genre, runtime, release year, directors, and
  principal actor/actress IDs. Missing cast can also mean documentary participants
  were credited as themselves rather than actors.
- **Wikidata:** US country-of-origin confirmation plus optional language, dates,
  and budget. Country is required to establish US eligibility even if it is not
  used as a model predictor. Coverage limits the population to documented US titles.
- Include IMDb types **movie** and **tvMovie** with ratings. Exclude other types:
  short, tvShort, video, tvSpecial, tvSeries, tvMiniSeries, tvEpisode, videoGame,
  and tvPilot. A video can be a film; excluding that category is our scope choice.
- US means country of origin includes United States (Q30), including co-productions.
  English language, a US title region, or a US release alone does not qualify.
  Missing country and ambiguous links are held out rather than guessed.
- Use **IMDb startYear** for filtering and planned splits: 2016-2023 training,
  2024 validation, 2025 testing. Use a Wikidata release month only when its selected
  earliest recorded date agrees with IMDb's year. Leave unknown months blank.
- Do not exclude movies merely for missing optional features. No missing-value
  filling, minimum vote threshold, or adult-content filter has been applied.
- Ratings are snapshots, not ratings at release. Vote count is not a pre-release
  predictor. We still need to justify pre-release feature availability, encode
  categories, and fit preprocessing on training data only.

## Current missing values

| Feature | Missing out of 10,000 |
|---|---:|
| Rating / IMDb year / country | 0 (required by selection) |
| Runtime | 66 |
| Genre | 11 |
| Director | 25 |
| Principal actor/actress cast | 1,696 |
| Language | 3,794 |
| Release month | 6,188 |
| Budget | 9,278 |

Next choose features and missing-value rules, then compare a mean baseline,
Ridge, and Random Forest using validation MAE. Keep testing for final evaluation.
Budgets retain their source amounts and currencies; no conversion is implemented.

## Short history: what we tried and removed

We started with 19 Wikidata movies, tested a 100-movie worldwide pilot, expanded
to about 2,000 US candidates, and then built the current 10,000 US-only dataset.
We chose US-only after exploring data coverage; the old archive, worldwide pilot
files, duplicate outputs, and reports folder have now been removed. Their useful
findings are summarized here instead of keeping several competing workflows.

The exploratory comparison used **100 worldwide and 100 US movies**, ten per year:

| Feature | Worldwide missing | US missing |
|---|---:|---:|
| Runtime | 8% | 0% |
| Genre | 1% | 0% |
| Director | 1% | 0% |
| Principal cast | 18% | 15% |
| Language | 82% | 47% |
| Country | 60% | 0% |
| Month | 86% | 71% |
| Budget | 99% | 95% |

This was preliminary: US records required a Wikidata country match, while only
40% of the worldwide sample matched Wikidata. Equal size and years do not remove
that selection difference. Worldwide also included US movies. The comparison
does not prove US films inherently have better data or easier-to-predict ratings.
A separate 1,000-candidate worldwide lookup was stopped during an outage and is
not part of our current dataset; those incomplete files were removed too.

**Why release_overrides.json was removed:** it stored one manual festival-date
correction for The Man with Hare Ears (2020 rather than a later 2021 release).
That film is outside the US-only sample, the override affected none of our 10,000
records, and IMDb year is now authoritative. The unused correction file and its
special-case code were removed. Original optional dates remain in the cache.

## GitHub and source conditions

All data/, caches, source downloads, and derived tables are ignored by Git except
empty folder placeholders. Share code and documentation; clear data-bearing
notebook outputs before publishing. Gitignore does not untrack earlier commits.

- [IMDb downloads and schema](https://data.imdb.com/non-commercial-datasets/)
- [IMDb use conditions](https://help.imdb.com/article/imdb/general-information/can-i-use-imdb-data-in-my-software/G5JTRESSHJBBHTGX)
- [Wikidata CC0 licensing](https://www.wikidata.org/wiki/Wikidata:Licensing)

IMDb files are original-source but prepackaged; merging/preprocessing is our work.
The group reports pitch approval. Specific group ML-use permission has not been
independently confirmed; keeping files out of Git is not a license clearance.
No IMDb scraping, TMDB, Kaggle, or Hugging Face data is used.

Information courtesy of IMDb (https://www.imdb.com). Used with permission.

That is IMDb's requested attribution wording, not a claim of a separate agreement.
