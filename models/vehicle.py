from utils.exceptions import ParkingError


class Vehicle:
    """Common data for every vehicle that parks."""

    def __init__(self, registration_number, owner_name):
        self._registration_number = registration_number
        self._owner_name = owner_name

    @property
    def registration_number(self):
        return self._registration_number

    @property
    def owner_name(self):
        return self._owner_name

    def get_type(self):
        return "Vehicle"

    # Subclasses replace this with their own price.
    def get_hourly_rate(self):
        return 0

    @classmethod
    def create(cls, vehicle_type, registration_number, owner_name):
        kind = (vehicle_type or "").strip().lower()
        classes = {
            "car": Car,
            "motorcycle": Motorcycle,
            "van": Van,
        }
        if kind not in classes:
            raise ParkingError("Vehicle type must be Car, Motorcycle, or Van.")
        return classes[kind](registration_number, owner_name)


class Car(Vehicle):
    def get_type(self):
        return "Car"

    def get_hourly_rate(self):
        return 50


class Motorcycle(Vehicle):
    def get_type(self):
        return "Motorcycle"

    def get_hourly_rate(self):
        return 30


class Van(Vehicle):
    def get_type(self):
        return "Van"

    def get_hourly_rate(self):
        return 70
