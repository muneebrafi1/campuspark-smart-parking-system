"""Vehicle types that can park at CampusPark.

Vehicle is the parent. Car, Motorcycle, and Van are children.
A child inherits the registration number and owner name, and it
overrides the three methods that describe that kind of vehicle.

The numbers returned by get_hourly_rate are the starting prices.
An admin can change the live price in the database. PaymentCalculator
uses the saved price when there is one.
"""

from utils.exceptions import ValidationError


class Vehicle:
    """Common data for every vehicle. Do not park a plain Vehicle.

    Subclasses must override get_vehicle_type, get_hourly_rate,
    and get_description. The base methods raise NotImplementedError
    so a forgotten override is obvious.
    """

    def __init__(self, registration_number, owner_name):
        if not str(registration_number).strip() or not str(owner_name).strip():
            raise ValidationError("Vehicle registration and owner name are required.")
        # Leading underscore means "please use the property, not this name".
        self._registration_number = str(registration_number).strip()
        self._owner_name = str(owner_name).strip()

    @property
    def registration_number(self):
        return self._registration_number

    @property
    def owner_name(self):
        return self._owner_name

    def get_vehicle_type(self):
        raise NotImplementedError("Each vehicle subclass must name its type.")

    def get_hourly_rate(self):
        raise NotImplementedError("Each vehicle subclass must give a default hourly rate.")

    def get_description(self):
        raise NotImplementedError("Each vehicle subclass must describe itself.")

    @classmethod
    def create(cls, vehicle_type, registration_number, owner_name):
        """Build the right subclass from the type chosen on the form.

        The caller can pass "car" or "Car". The object itself always
        reports the official type through get_vehicle_type().
        """
        key = (vehicle_type or "").strip().lower()
        mapping = {
            "car": Car,
            "motorcycle": Motorcycle,
            "van": Van,
        }
        subclass = mapping.get(key)
        if subclass is None:
            raise ValidationError("Vehicle type must be Car, Motorcycle, or Van.")
        return subclass(registration_number, owner_name)

    @staticmethod
    def default_rates():
        """Ask each subclass for its starting price.

        This is polymorphism: the loop treats every object as a Vehicle,
        and each subclass answers get_hourly_rate in its own way.
        """
        samples = (
            Car("SAMPLE", "Sample Owner"),
            Motorcycle("SAMPLE", "Sample Owner"),
            Van("SAMPLE", "Sample Owner"),
        )
        return {vehicle.get_vehicle_type(): vehicle.get_hourly_rate() for vehicle in samples}

    def __repr__(self):
        return (
            f"{self.__class__.__name__}("
            f"{self._registration_number!r}, {self._owner_name!r})"
        )


class Car(Vehicle):
    """A normal four-wheel campus vehicle. Default rate: PKR 50 per hour."""

    def get_vehicle_type(self):
        return "Car"

    def get_hourly_rate(self):
        return 50

    def get_description(self):
        return "Car — a standard campus vehicle"


class Motorcycle(Vehicle):
    """A two-wheeler. Default rate: PKR 30 per hour."""

    def get_vehicle_type(self):
        return "Motorcycle"

    def get_hourly_rate(self):
        return 30

    def get_description(self):
        return "Motorcycle — a two-wheeler"


class Van(Vehicle):
    """A larger campus vehicle. Default rate: PKR 70 per hour."""

    def get_vehicle_type(self):
        return "Van"

    def get_hourly_rate(self):
        return 70

    def get_description(self):
        return "Van — a larger campus vehicle"
