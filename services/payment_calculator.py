from datetime import datetime

from utils.exceptions import ParkingError


def format_duration(seconds):
    seconds = int(seconds)
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours and minutes:
        return f"{hours}h {minutes}m"
    if hours:
        return f"{hours}h"
    if minutes:
        return f"{minutes}m"
    return f"{secs}s"


class PaymentCalculator:
    """Turns entry and exit times into a bill."""

    def __init__(self, rates):
        # Copy so the caller cannot change our rates later.
        self._rates = dict(rates)

    @property
    def rates(self):
        return dict(self._rates)

    def rate_for(self, vehicle):
        vehicle_type = vehicle.get_type()
        if vehicle_type in self._rates:
            return float(self._rates[vehicle_type])
        return float(vehicle.get_hourly_rate())

    def billable_hours(self, entry_time, exit_time):
        if not isinstance(entry_time, datetime) or not isinstance(exit_time, datetime):
            raise ParkingError("Entry and exit times must be real dates and times.")
        if exit_time < entry_time:
            raise ParkingError("Exit time cannot be earlier than the entry time.")

        seconds = int((exit_time - entry_time).total_seconds())
        # Less than or equal to one hour, including leaving straight away, is 1 hour.
        if seconds <= 3600:
            return 1
        if seconds % 3600 == 0:
            return seconds // 3600
        return seconds // 3600 + 1

    def calculate(self, vehicle, entry_time, exit_time):
        hours = self.billable_hours(entry_time, exit_time)
        rate = self.rate_for(vehicle)
        seconds = int((exit_time - entry_time).total_seconds())
        return {
            "entry_time": entry_time,
            "exit_time": exit_time,
            "duration_text": format_duration(seconds),
            "billable_hours": hours,
            "hourly_rate": rate,
            "total": round(hours * rate, 2),
            "vehicle_type": vehicle.get_type(),
        }
