"""The slip created when a vehicle enters.

While the vehicle is inside, status is 'parked'. After exit, close()
stores the fee on this object and the status becomes 'completed'.
The matching payment row is written by DatabaseManager.
"""

from utils.exceptions import ValidationError


class ParkingTicket:
    """One visit, from entry until the fee is paid and the slot is free."""

    def __init__(
        self,
        ticket_id,
        registration_number,
        owner_name,
        vehicle_type,
        slot_number,
        entry_time,
        exit_time=None,
        duration_text=None,
        billable_hours=None,
        hourly_rate=None,
        fee=None,
        status="parked",
    ):
        if not ticket_id:
            raise ValidationError("A ticket needs an ID.")
        if status not in ("parked", "completed"):
            raise ValidationError("Ticket status must be parked or completed.")
        self._ticket_id = ticket_id
        self._registration_number = registration_number
        self._owner_name = owner_name
        self._vehicle_type = vehicle_type
        self._slot_number = slot_number
        self._entry_time = entry_time
        self._exit_time = exit_time
        self._duration_text = duration_text
        self._billable_hours = billable_hours
        self._hourly_rate = hourly_rate
        self._fee = fee
        self._status = status

    @property
    def ticket_id(self):
        return self._ticket_id

    @property
    def registration_number(self):
        return self._registration_number

    @property
    def owner_name(self):
        return self._owner_name

    @property
    def vehicle_type(self):
        return self._vehicle_type

    @property
    def slot_number(self):
        return self._slot_number

    @property
    def entry_time(self):
        return self._entry_time

    @property
    def exit_time(self):
        return self._exit_time

    @property
    def duration_text(self):
        return self._duration_text

    @property
    def billable_hours(self):
        return self._billable_hours

    @property
    def hourly_rate(self):
        return self._hourly_rate

    @property
    def fee(self):
        return self._fee

    @property
    def status(self):
        return self._status

    @property
    def is_active(self):
        return self._status == "parked"

    def close(self, exit_time, duration_text, billable_hours, hourly_rate, fee):
        """Finish the visit. A closed ticket cannot be closed again."""
        if not self.is_active:
            raise ValidationError(f"Ticket {self._ticket_id} is already closed.")
        self._exit_time = exit_time
        self._duration_text = duration_text
        self._billable_hours = billable_hours
        self._hourly_rate = hourly_rate
        self._fee = fee
        self._status = "completed"
        return self

    def __repr__(self):
        return f"ParkingTicket({self._ticket_id!r}, {self._status!r})"
