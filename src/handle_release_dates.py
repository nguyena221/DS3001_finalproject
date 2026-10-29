"""Interpret supplemental Wikidata dates and map IMDb years to split labels.

Imported by the merge helper; never changes the original source records.
"""

import calendar
import re
from datetime import date
GREGORIAN = "Q1985727"


def date_interval(value):
    """A year-only date covers a year, not an invented January release."""
    match = re.fullmatch(r"\+(\d{4})-(\d{2})-(\d{2})T00:00:00Z", value["time"])
    if not match or not value.get("calendarmodel", "").endswith(GREGORIAN):
        raise ValueError("unsupported date or calendar")
    if value.get("before", 0) or value.get("after", 0):
        raise ValueError("uncertain date bounds")
    year, month, day = map(int, match.groups())
    precision = value["precision"]
    if precision == 9:
        return date(year, 1, 1), date(year, 12, 31)
    if precision == 10:
        return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
    if precision == 11:
        exact = date(year, month, day)
        return exact, exact
    raise ValueError("unsupported date precision")


def choose_release(statements):
    result = dict(release_date="", release_precision="", release_year="",
                  release_month="", release_date_review="")
    if not statements:
        result["release_date_review"] = "No known release date"
        return result
    try:
        intervals = [date_interval(s["value"]) for s in statements]
    except (KeyError, TypeError, ValueError) as error:
        result["release_date_review"] = f"Manual review required: {error}"
        return result
    # The earliest release lies between the smallest lower and upper bounds.
    earliest = min(start for start, end in intervals)
    latest = min(end for start, end in intervals)
    if earliest.year != latest.year:
        result["release_date_review"] = "Earliest release year is ambiguous"
        return result
    result["release_year"] = earliest.year
    result["release_date"] = str(earliest.year)
    result["release_precision"] = "year"
    if earliest.month == latest.month:
        result["release_month"] = earliest.month
        result["release_date"] = earliest.strftime("%Y-%m")
        result["release_precision"] = "month"
        if earliest == latest:
            result["release_date"] = earliest.isoformat()
            result["release_precision"] = "day"
    if earliest != latest:
        result["release_date_review"] = "First release has limited precision; finer date parts left missing"
    return result


def split_for_year(year):
    if year == "":
        return "review"
    if 2016 <= year <= 2023:
        return "train"
    if year == 2024:
        return "validation"
    if year == 2025:
        return "test"
    return "outside_scope"
