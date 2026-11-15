from utils.exceptions import BillingError


class MeterReading:
    """Previous and current meter numbers for one month."""

    def __init__(self, month, previous_reading, current_reading, customer_id=None, reading_id=None):
        if previous_reading < 0 or current_reading < 0:
            raise BillingError("Readings cannot be negative.")
        if current_reading < previous_reading:
            raise BillingError("Current reading cannot be less than the previous reading.")
        self._month = month
        self._previous = float(previous_reading)
        self._current = float(current_reading)
        self._customer_id = customer_id
        self._id = reading_id

    @property
    def month(self):
        return self._month

    @property
    def previous_reading(self):
        return self._previous

    @property
    def current_reading(self):
        return self._current

    @property
    def customer_id(self):
        return self._customer_id

    @property
    def reading_id(self):
        return self._id

    @property
    def units(self):
        return round(self._current - self._previous, 2)
