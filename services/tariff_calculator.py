from datetime import date, timedelta


# Starting prices. The Tariff page can change the copies stored in the database.
DEFAULT_TARIFFS = {
    "Domestic": {
        "slab1_units": 100, "slab1_rate": 10,
        "slab2_units": 100, "slab2_rate": 20,
        "slab3_rate": 30,
        "fixed_charge": 100, "tax_percent": 10,
    },
    "Commercial": {
        "slab1_units": 100, "slab1_rate": 20,
        "slab2_units": 0, "slab2_rate": 40,
        "slab3_rate": 0,
        "fixed_charge": 200, "tax_percent": 10,
    },
}
DEFAULT_LATE_PERCENT = 10
DEFAULT_DUE_DAYS = 15


class TariffCalculator:
    """Asks the customer object for the energy charge, then adds fixed, tax, and late fee."""

    def __init__(self, tariffs, late_percent, due_days):
        self._tariffs = tariffs
        self._late_percent = float(late_percent)
        self._due_days = int(due_days)

    @property
    def late_percent(self):
        return self._late_percent

    @property
    def due_days(self):
        return self._due_days

    def due_date_for(self, month):
        year, mon = [int(part) for part in month.split("-")]
        if mon == 12:
            first_next = date(year + 1, 1, 1)
        else:
            first_next = date(year, mon + 1, 1)
        # 15 due days means the 15th of the next month.
        return first_next + timedelta(days=self._due_days - 1)

    def quote(self, customer, units, month, on_date):
        rates = self._tariffs[customer.get_connection_type()]
        # Polymorphic call: Domestic and Commercial price units differently.
        energy = customer.energy_charge(units, rates)
        fixed = round(float(rates["fixed_charge"]), 2)
        tax = round((energy + fixed) * float(rates["tax_percent"]) / 100, 2)
        due = self.due_date_for(month)
        base = round(energy + fixed + tax, 2)
        surcharge = 0.0
        if on_date > due:
            surcharge = round(base * self._late_percent / 100, 2)
        return {
            "energy_charge": energy,
            "fixed_charge": fixed,
            "tax_amount": tax,
            "surcharge": surcharge,
            "total": round(base + surcharge, 2),
            "due_date": due,
        }
