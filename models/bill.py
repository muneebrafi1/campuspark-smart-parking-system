from utils.exceptions import BillingError


class Bill:
    """One month's bill for a customer."""

    def __init__(self, bill_no, customer_id, month, units, energy_charge, fixed_charge,
                 tax_amount, surcharge, total, due_date, status="unpaid", paid_date=None):
        self._bill_no = bill_no
        self._customer_id = customer_id
        self._month = month
        self._units = units
        self._energy_charge = energy_charge
        self._fixed_charge = fixed_charge
        self._tax_amount = tax_amount
        self._surcharge = surcharge
        self._total = total
        self._due_date = due_date
        self._status = status
        self._paid_date = paid_date

    @property
    def bill_no(self):
        return self._bill_no

    @property
    def month(self):
        return self._month

    @property
    def energy_charge(self):
        return self._energy_charge

    @property
    def fixed_charge(self):
        return self._fixed_charge

    @property
    def tax_amount(self):
        return self._tax_amount

    @property
    def due_date(self):
        return self._due_date

    @property
    def status(self):
        return self._status

    @property
    def total(self):
        return self._total

    @property
    def surcharge(self):
        return self._surcharge

    @property
    def is_paid(self):
        return self._status == "paid"

    def mark_paid(self, paid_date, surcharge, total):
        if self.is_paid:
            raise BillingError(f"Bill {self._bill_no} is already paid.")
        self._paid_date = paid_date
        self._surcharge = surcharge
        self._total = total
        self._status = "paid"
        return self
