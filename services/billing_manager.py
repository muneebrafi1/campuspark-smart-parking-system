from datetime import date, datetime

from database.database_manager import DatabaseManager
from models.bill import Bill
from models.customer import Customer
from models.meter_reading import MeterReading
from services.tariff_calculator import DEFAULT_DUE_DAYS, DEFAULT_LATE_PERCENT, DEFAULT_TARIFFS, TariffCalculator
from utils.exceptions import BillingError


def clean_name(value):
    name = " ".join(str(value or "").split())
    if len(name) < 3 or any(not (ch.isalpha() or ch in " .'-") for ch in name):
        raise BillingError("Enter the customer name using letters.")
    return name


def clean_cnic(value):
    text = str(value or "").strip()
    digits = [ch for ch in text if ch.isdigit()]
    if len(digits) < 5 or any(ch not in "0123456789- " for ch in text):
        raise BillingError("Enter a CNIC or ID number.")
    return text


def clean_address(value):
    address = " ".join(str(value or "").split())
    if len(address) < 5:
        raise BillingError("Enter the address.")
    return address


def clean_phone(value):
    phone = str(value or "").strip()
    if sum(ch.isdigit() for ch in phone) < 7:
        raise BillingError("Enter a phone number.")
    return phone


def clean_meter(value):
    meter = str(value or "").strip().upper()
    if len(meter) < 3 or any(not (ch.isalnum() or ch == "-") for ch in meter):
        raise BillingError("Meter number should be at least 3 letters or digits.")
    return meter


def clean_month(value):
    text = str(value or "").strip()
    parts = text.split("-")
    if len(parts) != 2 or len(parts[0]) != 4 or not parts[0].isdigit() or not parts[1].isdigit():
        raise BillingError("Month should look like 2026-11.")
    month = int(parts[1])
    if not 1 <= month <= 12:
        raise BillingError("Month should look like 2026-11.")
    return f"{int(parts[0]):04d}-{month:02d}"


def clean_number(value, label):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise BillingError(f"{label} must be a number.")
    return number


class BillingManager:
    """Customers, readings, and bills. It uses the database and the tariff calculator."""

    def __init__(self, db_path):
        self._db = DatabaseManager(db_path)
        self._db.seed_if_empty(DEFAULT_TARIFFS, DEFAULT_LATE_PERCENT, DEFAULT_DUE_DAYS)

    @property
    def database(self):
        return self._db

    def close(self):
        self._db.close()

    def _calculator(self):
        return TariffCalculator(
            self._db.get_tariffs(),
            self._db.get_setting("late_percent"),
            self._db.get_setting("due_days"),
        )

    def add_customer(self, name, cnic, address, phone, meter_number, connection_type):
        customer = self._build_customer(name, cnic, address, phone, meter_number, connection_type)
        customer_id = self._db.insert_customer(
            customer.name, customer.cnic, customer.address, customer.phone,
            customer.meter_number, customer.get_connection_type(),
        )
        return self._db.get_customer(customer_id)

    def update_customer(self, customer_id, name, cnic, address, phone, meter_number, connection_type):
        if self._db.get_customer(customer_id) is None:
            raise BillingError("Customer was not found.")
        customer = self._build_customer(name, cnic, address, phone, meter_number, connection_type)
        self._db.update_customer(
            customer_id, customer.name, customer.cnic, customer.address, customer.phone,
            customer.meter_number, customer.get_connection_type(),
        )
        return self._db.get_customer(customer_id)

    def delete_customer(self, customer_id):
        self._db.delete_customer(customer_id)

    def search_customers(self, text=""):
        return self._db.search_customers(text)

    def add_reading(self, customer_id, month, previous_reading, current_reading, on_date=None):
        row = self._db.get_customer(customer_id)
        if row is None:
            raise BillingError("Customer was not found.")
        month = clean_month(month)
        if self._db.reading_for_month(customer_id, month):
            raise BillingError("This month already has a reading for that meter.")
        previous = clean_number(previous_reading, "Previous reading")
        current = clean_number(current_reading, "Current reading")
        reading = MeterReading(month, previous, current, customer_id)
        customer = Customer.create(
            row["connection_type"], row["name"], row["cnic"], row["address"],
            row["phone"], row["meter_number"], row["id"],
        )
        on_date = on_date or date.today()
        quote = self._calculator().quote(customer, reading.units, month, on_date)
        bill_no = self._db.next_bill_no()
        bill = Bill(
            bill_no, customer_id, month, reading.units, quote["energy_charge"],
            quote["fixed_charge"], quote["tax_amount"], quote["surcharge"],
            quote["total"], quote["due_date"],
        )
        self._db.save_reading_and_bill(customer_id, reading, bill)
        saved = self._db.get_bill(bill_no)
        return self._with_amount(saved, on_date)

    def bills(self, search="", month="", status="All", on_date=None):
        today = on_date or date.today()
        month = clean_month(month) if month else ""
        found = []
        for row in self._db.list_bills():
            if month and row["month"] != month:
                continue
            blob = f"{row['name']} {row['meter_number']} {row['bill_no']}".lower()
            if search and search.strip().lower() not in blob:
                continue
            item = self._with_amount(row, today)
            if status == "Unpaid" and item["status"] != "unpaid":
                continue
            if status == "Paid" and item["status"] != "paid":
                continue
            if status == "Overdue" and not item["overdue"]:
                continue
            found.append(item)
        return found

    def mark_paid(self, bill_no, pay_date=None):
        row = self._db.get_bill(bill_no)
        if row is None:
            raise BillingError("Bill was not found.")
        if row["status"] == "paid":
            raise BillingError(f"Bill {bill_no} is already paid.")
        pay_date = pay_date or date.today()
        if isinstance(pay_date, datetime):
            pay_date = pay_date.date()
        view = self._with_amount(row, pay_date)
        bill = Bill(
            row["bill_no"], row["customer_id"], row["month"], row["units"],
            row["energy_charge"], row["fixed_charge"], row["tax_amount"],
            row["surcharge"], row["total"], date.fromisoformat(row["due_date"]),
            row["status"],
        )
        bill.mark_paid(pay_date, view["surcharge"], view["amount_due"])
        self._db.mark_bill_paid(bill.bill_no, bill.surcharge, bill.total, pay_date.isoformat())
        return self._with_amount(self._db.get_bill(bill_no), pay_date)

    def dashboard(self, on_date=None):
        today = on_date or date.today()
        this_month = today.strftime("%Y-%m")
        bills = [self._with_amount(row, today) for row in self._db.list_bills()]
        customers = self._db.search_customers("")
        collected = sum(bill["total"] for bill in bills if bill["status"] == "paid")
        pending = sum(bill["amount_due"] for bill in bills if bill["status"] == "unpaid")
        by_month = {}
        for bill in bills:
            by_month[bill["month"]] = by_month.get(bill["month"], 0) + bill["amount_due"]
        by_type = {"Domestic": 0, "Commercial": 0}
        for customer in customers:
            by_type[customer["connection_type"]] = by_type.get(customer["connection_type"], 0) + 1
        return {
            "customers": len(customers),
            "bills_this_month": sum(1 for bill in bills if bill["month"] == this_month),
            "total_billed": round(collected + pending, 2),
            "collected": round(collected, 2),
            "pending": round(pending, 2),
            "by_month": [{"month": key, "amount": round(value, 2)} for key, value in sorted(by_month.items())],
            "by_type": [{"connection_type": key, "customers": value} for key, value in by_type.items()],
        }

    def get_tariffs(self):
        calc = self._calculator()
        return {
            "tariffs": self._db.get_tariffs(),
            "late_percent": calc.late_percent,
            "due_days": calc.due_days,
        }

    def update_tariffs(self, tariffs, late_percent, due_days):
        cleaned = {}
        for name in ("Domestic", "Commercial"):
            if name not in tariffs:
                raise BillingError(f"Missing tariff for {name}.")
            cleaned[name] = self._clean_rates(tariffs[name])
        late = clean_number(late_percent, "Late surcharge")
        days = clean_number(due_days, "Due days")
        if not 0 <= late <= 100:
            raise BillingError("Late surcharge should be between 0 and 100.")
        if not 1 <= days <= 60:
            raise BillingError("Due days should be between 1 and 60.")
        for name, rates in cleaned.items():
            self._db.update_tariff(name, rates)
        self._db.update_setting("late_percent", late)
        self._db.update_setting("due_days", int(days))
        return self.get_tariffs()

    def _build_customer(self, name, cnic, address, phone, meter_number, connection_type):
        return Customer.create(
            connection_type, clean_name(name), clean_cnic(cnic), clean_address(address),
            clean_phone(phone), clean_meter(meter_number),
        )

    def _clean_rates(self, rates):
        number_fields = (
            "slab1_units", "slab1_rate", "slab2_units", "slab2_rate",
            "slab3_rate", "fixed_charge", "tax_percent",
        )
        cleaned = {}
        for field in number_fields:
            cleaned[field] = clean_number(rates.get(field), field)
            if cleaned[field] < 0:
                raise BillingError("Tariff numbers cannot be negative.")
        if not 0 <= cleaned["tax_percent"] <= 100:
            raise BillingError("Tax percent should be between 0 and 100.")
        return cleaned

    def _with_amount(self, row, on_date):
        item = dict(row)
        if isinstance(on_date, datetime):
            on_date = on_date.date()
        due = date.fromisoformat(item["due_date"])
        base = round(item["energy_charge"] + item["fixed_charge"] + item["tax_amount"], 2)
        if item["status"] == "paid":
            item["amount_due"] = item["total"]
            item["overdue"] = False
            return item
        late = 0.0
        item["overdue"] = on_date > due
        if item["overdue"]:
            late = round(base * self._calculator().late_percent / 100, 2)
        item["surcharge"] = late
        item["amount_due"] = round(base + late, 2)
        return item
