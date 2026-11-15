from utils.exceptions import BillingError


def slab_cost(units, bands):
    """bands is a list of (units in this band, rate). None means the rest."""
    left = float(units)
    cost = 0.0
    for limit, rate in bands:
        if left <= 0:
            break
        take = left if limit is None else min(left, float(limit))
        cost += take * float(rate)
        left -= take
    return round(cost, 2)


class Customer:
    """Shared customer data. Subclasses decide the energy charge."""

    def __init__(self, name, cnic, address, phone, meter_number, customer_id=None):
        self._id = customer_id
        self._name = name
        self._cnic = cnic
        self._address = address
        self._phone = phone
        self._meter_number = meter_number

    @property
    def customer_id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @property
    def cnic(self):
        return self._cnic

    @property
    def address(self):
        return self._address

    @property
    def phone(self):
        return self._phone

    @property
    def meter_number(self):
        return self._meter_number

    def get_connection_type(self):
        raise NotImplementedError("Each connection type must name itself.")

    def energy_charge(self, units, rates):
        # Abstract: Domestic and Commercial replace this.
        raise NotImplementedError("Each connection type must price its units.")

    @classmethod
    def create(cls, connection_type, name, cnic, address, phone, meter_number, customer_id=None):
        kind = (connection_type or "").strip().lower()
        classes = {"domestic": DomesticCustomer, "commercial": CommercialCustomer}
        if kind not in classes:
            raise BillingError("Connection type must be Domestic or Commercial.")
        return classes[kind](name, cnic, address, phone, meter_number, customer_id)


class DomesticCustomer(Customer):
    def get_connection_type(self):
        return "Domestic"

    def energy_charge(self, units, rates):
        # Three bands: first slab, second slab, then everything above.
        return slab_cost(units, [
            (rates["slab1_units"], rates["slab1_rate"]),
            (rates["slab2_units"], rates["slab2_rate"]),
            (None, rates["slab3_rate"]),
        ])


class CommercialCustomer(Customer):
    def get_connection_type(self):
        return "Commercial"

    def energy_charge(self, units, rates):
        # Two bands: a first block, then one rate for the rest.
        return slab_cost(units, [
            (rates["slab1_units"], rates["slab1_rate"]),
            (None, rates["slab2_rate"]),
        ])
