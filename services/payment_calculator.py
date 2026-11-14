"""Turns a stay into a bill.

Policy, in plain words:
- Time is measured from entry to exit.
- Any minute past a full hour starts another billed hour (round up).
- The smallest bill is 1 hour, even if the vehicle leaves immediately.
- Exactly 2 hours is billed as 2 hours, not 3.
- The price per hour comes from the saved rates when we have them.
  Otherwise we ask the vehicle object, which is polymorphism.
"""

from datetime import datetime

from utils.exceptions import ValidationError
from utils.helpers import format_duration


class PaymentCalculator:
    """Knows the hourly rates and the rounding rule. It does not touch the database."""

    MINIMUM_BILLABLE_HOURS = 1
    POLICY_TEXT = (
        "Minimum charge is 1 hour. Any partial hour is rounded up to the next hour."
    )

    def __init__(self, rates):
        if not isinstance(rates, dict) or not rates:
            raise ValidationError("Pricing rates are missing.")
        # Copy the numbers so a caller cannot change them behind our back.
        self._rates = {vehicle_type: float(rate) for vehicle_type, rate in rates.items()}

    @property
    def rates(self):
        """A copy of the rates this calculator was given."""
        return dict(self._rates)

    def rate_for(self, vehicle):
        """Price per hour for this vehicle.

        The saved admin rate wins. If that type has no saved rate, we call
        vehicle.get_hourly_rate(). Car, Motorcycle, and Van each override
        that method.
        """
        vehicle_type = vehicle.get_vehicle_type()
        if vehicle_type in self._rates:
            return float(self._rates[vehicle_type])
        return float(vehicle.get_hourly_rate())

    def billable_hours(self, entry_time, exit_time):
        """Whole hours to charge. Always at least 1."""
        if not isinstance(entry_time, datetime) or not isinstance(exit_time, datetime):
            raise ValidationError("Entry and exit times must be valid dates and times.")
        if exit_time < entry_time:
            raise ValidationError("Exit time cannot be earlier than the entry time.")

        seconds = int((exit_time - entry_time).total_seconds())
        if seconds <= 0:
            return self.MINIMUM_BILLABLE_HOURS
        # Integer maths avoids a float rounding surprise on exact hours.
        if seconds % 3600 == 0:
            hours = seconds // 3600
        else:
            hours = (seconds // 3600) + 1
        if hours < self.MINIMUM_BILLABLE_HOURS:
            return self.MINIMUM_BILLABLE_HOURS
        return hours

    def calculate(self, vehicle, entry_time, exit_time):
        """Return the breakdown shown on the exit screen."""
        hours = self.billable_hours(entry_time, exit_time)
        rate = self.rate_for(vehicle)
        amount = round(hours * rate, 2)
        duration = exit_time - entry_time
        return {
            "entry_time": entry_time,
            "exit_time": exit_time,
            "duration": duration,
            "duration_text": format_duration(duration),
            "billable_hours": hours,
            "hourly_rate": rate,
            "total_amount": amount,
            "vehicle_type": vehicle.get_vehicle_type(),
            "policy": self.POLICY_TEXT,
        }
