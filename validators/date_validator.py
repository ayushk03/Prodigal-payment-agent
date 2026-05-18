"""Date parsing and validation — handles leap years correctly."""
import re
from datetime import date


def validate_date(date_str: str) -> bool:
    """
    Validate a YYYY-MM-DD date string.
    Crucially handles leap years: 1988-02-29 → valid, 1989-02-29 → invalid.
    """
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return False
    try:
        year, month, day = map(int, date_str.split("-"))
        date(year, month, day)  # raises ValueError on impossible dates
        return True
    except ValueError:
        return False


def is_reasonable_dob(date_str: str) -> bool:
    """Check the date is valid and a plausible date of birth (in the past)."""
    if not validate_date(date_str):
        return False
    year, month, day = map(int, date_str.split("-"))
    dob = date(year, month, day)
    return dob < date.today()
