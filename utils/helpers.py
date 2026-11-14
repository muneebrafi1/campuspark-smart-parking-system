"""Small functions used by more than one part of the app.

Keeping them here means the fee rules and the pages format time and
money the same way.
"""

import re
from datetime import datetime

from utils.exceptions import ValidationError

# A campus lot of this size is created the first time the database opens.
DEFAULT_SLOT_COUNT = 20

# Stored in SQLite as text so a later query can sort visits by time.
DATETIME_FMT = "%Y-%m-%d %H:%M:%S"

VEHICLE_TYPES = ("Car", "Motorcycle", "Van")

# 3 to 15 characters. Letters, numbers, spaces, and hyphens only.
_REGISTRATION_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9\- ]{1,13}[A-Z0-9]$")

# 3 to 60 characters. Letters plus a few marks used in names.
_OWNER_PATTERN = re.compile(r"^[A-Za-z][A-Za-z .'\-]{1,58}[A-Za-z.]$")


def normalize_registration(value):
    """Return a clean registration number, or raise if it is unusable.

    "lea 4521" and "LEA-4521" become one stored form so the same car
    cannot sneak in under a different spelling.
    """
    if value is None:
        raise ValidationError("Registration number is required.")
    cleaned = " ".join(str(value).strip().upper().split())
    if not _REGISTRATION_PATTERN.fullmatch(cleaned):
        raise ValidationError(
            "Registration number must be 3–15 characters and use only "
            "letters, numbers, spaces, or hyphens."
        )
    return cleaned


def normalize_owner_name(value):
    """Return a clean owner name, or raise if it is empty or too odd."""
    if value is None:
        raise ValidationError("Owner name is required.")
    cleaned = " ".join(str(value).strip().split())
    if not _OWNER_PATTERN.fullmatch(cleaned):
        raise ValidationError(
            "Owner name must be 3–60 characters and use only letters, "
            "spaces, apostrophes, periods, or hyphens."
        )
    return cleaned


def format_timestamp(value):
    """Turn a datetime into the text we store in SQLite."""
    return value.strftime(DATETIME_FMT)


def parse_timestamp(value):
    """Turn stored text (or a datetime) back into a datetime."""
    if isinstance(value, datetime):
        return value.replace(microsecond=0)
    return datetime.strptime(value, DATETIME_FMT)


def format_display_time(value):
    """Example: 14 Nov 2026, 09:30 AM. Empty values become an em dash."""
    if value is None or value == "":
        return "—"
    if isinstance(value, str):
        value = parse_timestamp(value)
    return value.strftime("%d %b %Y, %I:%M %p")


def format_duration(duration):
    """Short label such as '1h 20m'. A stay under a minute shows seconds."""
    if duration is None:
        return "—"
    total_seconds = int(duration.total_seconds())
    if total_seconds < 0:
        return "—"
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts)


def format_money(amount):
    """Pakistani Rupees, with grouping. None becomes an em dash."""
    if amount is None:
        return "—"
    value = float(amount)
    if value.is_integer():
        return f"PKR {value:,.0f}"
    return f"PKR {value:,.2f}"


def combine_date_and_time(day, clock):
    """Join the date widget and the time widget into one datetime."""
    return datetime.combine(day, clock).replace(second=0, microsecond=0)


def status_label(status):
    """Title-style label for a stored status word."""
    labels = {
        "parked": "Parked",
        "completed": "Completed",
        "available": "Available",
        "occupied": "Occupied",
    }
    return labels.get(status, str(status))
