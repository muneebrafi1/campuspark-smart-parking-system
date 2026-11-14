from utils.exceptions import ParkingError


class ParkingTicket:
    """The slip for one visit, from entry until the car leaves."""

    def __init__(self, ticket_id, registration_number, owner_name, vehicle_type,
                 slot_number, entry_time, exit_time=None, fee=None, status="parked"):
        self._ticket_id = ticket_id
        self._registration_number = registration_number
        self._owner_name = owner_name
        self._vehicle_type = vehicle_type
        self._slot_number = slot_number
        self._entry_time = entry_time
        self._exit_time = exit_time
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
    def fee(self):
        return self._fee

    @property
    def status(self):
        return self._status

    @property
    def is_active(self):
        return self._status == "parked"

    def close(self, exit_time, fee):
        if not self.is_active:
            raise ParkingError(f"Ticket {self._ticket_id} is already closed.")
        self._exit_time = exit_time
        self._fee = fee
        self._status = "completed"
        return self
