"""Errors a caller can show to the attendant.

These are ordinary Python exceptions. The user interface catches them
and prints the message. Nothing here talks to SQLite or Streamlit.
"""


class ParkingError(Exception):
    """Base class for CampusPark errors that the user can understand."""


class ValidationError(ParkingError):
    """The form is missing something or the value is not acceptable."""


class DuplicateVehicleError(ParkingError):
    """This registration is already inside the parking area."""


class ParkingFullError(ParkingError):
    """Every slot is occupied, so a new vehicle cannot enter."""


class VehicleNotFoundError(ParkingError):
    """No active visit matches the registration number or ticket ID."""


class DatabaseError(ParkingError):
    """SQLite could not open the file or finish a save."""
