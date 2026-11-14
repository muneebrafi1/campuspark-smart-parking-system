from utils.exceptions import ParkingError


class ParkingSlot:
    """One numbered space in the lot."""

    def __init__(self, slot_number, status="available", registration_number=None,
                 vehicle_type=None, ticket_id=None):
        self._slot_number = slot_number
        self._status = status
        self._registration_number = registration_number
        self._vehicle_type = vehicle_type
        self._ticket_id = ticket_id

    @property
    def slot_number(self):
        return self._slot_number

    @property
    def status(self):
        return self._status

    @property
    def registration_number(self):
        return self._registration_number

    @property
    def vehicle_type(self):
        return self._vehicle_type

    @property
    def ticket_id(self):
        return self._ticket_id

    @property
    def is_occupied(self):
        return self._status == "occupied"

    @property
    def is_available(self):
        return self._status == "available"

    def occupy(self, registration_number, vehicle_type, ticket_id):
        if self.is_occupied:
            raise ParkingError(f"Slot {self._slot_number} is already occupied.")
        self._status = "occupied"
        self._registration_number = registration_number
        self._vehicle_type = vehicle_type
        self._ticket_id = ticket_id

    def release(self):
        if self.is_available:
            raise ParkingError(f"Slot {self._slot_number} is already free.")
        self._status = "available"
        self._registration_number = None
        self._vehicle_type = None
        self._ticket_id = None
