"""One physical parking space.

The database stores the slot. This class is the in-memory object the
rest of the program uses, so the rules for occupying and releasing a
slot live in one place.
"""

from utils.exceptions import ValidationError


class ParkingSlot:
    """A numbered space that is either available or occupied."""

    def __init__(
        self,
        slot_number,
        status="available",
        registration_number=None,
        vehicle_type=None,
        ticket_id=None,
    ):
        if isinstance(slot_number, bool) or not isinstance(slot_number, int) or slot_number < 1:
            raise ValidationError("Slot number must be a positive whole number.")
        if status not in ("available", "occupied"):
            raise ValidationError("Slot status must be available or occupied.")
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
        """Mark this slot taken. Fails if a vehicle is already here."""
        if self.is_occupied:
            raise ValidationError(
                f"Slot {self._slot_number} is already occupied and cannot be assigned."
            )
        if not registration_number or not vehicle_type or not ticket_id:
            raise ValidationError("A slot needs a registration, vehicle type, and ticket.")
        self._status = "occupied"
        self._registration_number = registration_number
        self._vehicle_type = vehicle_type
        self._ticket_id = ticket_id

    def release(self):
        """Mark this slot open after a vehicle leaves."""
        if not self.is_occupied:
            raise ValidationError(f"Slot {self._slot_number} is already available.")
        self._status = "available"
        self._registration_number = None
        self._vehicle_type = None
        self._ticket_id = None

    def __repr__(self):
        return f"ParkingSlot({self._slot_number}, {self._status!r})"
