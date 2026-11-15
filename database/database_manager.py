import sqlite3
from pathlib import Path

from utils.exceptions import BillingError


class DatabaseManager:
    """All SQL for the billing app is in this class."""

    def __init__(self, db_path):
        self._db_path = str(db_path)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, timeout=10, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._create_tables()

    @property
    def db_path(self):
        return self._db_path

    def close(self):
        self._conn.close()

    def _one(self, sql, params=()):
        row = self._conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def _all(self, sql, params=()):
        return [dict(row) for row in self._conn.execute(sql, params).fetchall()]

    def _create_tables(self):
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, cnic TEXT NOT NULL,
                address TEXT NOT NULL, phone TEXT NOT NULL,
                meter_number TEXT NOT NULL UNIQUE, connection_type TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS meter_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL REFERENCES customers(id),
                month TEXT NOT NULL, previous_reading REAL NOT NULL,
                current_reading REAL NOT NULL, units REAL NOT NULL,
                UNIQUE (customer_id, month));
            CREATE TABLE IF NOT EXISTS bills (
                bill_no TEXT PRIMARY KEY,
                customer_id INTEGER NOT NULL REFERENCES customers(id),
                reading_id INTEGER NOT NULL UNIQUE REFERENCES meter_readings(id),
                month TEXT NOT NULL, units REAL NOT NULL,
                energy_charge REAL NOT NULL, fixed_charge REAL NOT NULL, tax_amount REAL NOT NULL,
                surcharge REAL NOT NULL, total REAL NOT NULL, due_date TEXT NOT NULL,
                status TEXT NOT NULL, paid_date TEXT);
            CREATE TABLE IF NOT EXISTS tariffs (
                connection_type TEXT PRIMARY KEY,
                slab1_units INTEGER NOT NULL, slab1_rate REAL NOT NULL,
                slab2_units INTEGER NOT NULL, slab2_rate REAL NOT NULL, slab3_rate REAL NOT NULL,
                fixed_charge REAL NOT NULL, tax_percent REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY, value REAL NOT NULL);
            """
        )
        self._conn.commit()

    def seed_if_empty(self, tariffs, late_percent, due_days):
        if self._conn.execute("SELECT COUNT(*) FROM tariffs").fetchone()[0] == 0:
            for name, rates in tariffs.items():
                self._conn.execute(
                    """INSERT INTO tariffs (
                        connection_type, slab1_units, slab1_rate, slab2_units, slab2_rate,
                        slab3_rate, fixed_charge, tax_percent
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (name, rates["slab1_units"], rates["slab1_rate"], rates["slab2_units"],
                     rates["slab2_rate"], rates["slab3_rate"], rates["fixed_charge"], rates["tax_percent"]),
                )
        if self._one("SELECT * FROM settings WHERE key = 'late_percent'") is None:
            self._conn.execute("INSERT INTO settings (key, value) VALUES ('late_percent', ?)", (late_percent,))
            self._conn.execute("INSERT INTO settings (key, value) VALUES ('due_days', ?)", (due_days,))
        self._conn.commit()

    def insert_customer(self, name, cnic, address, phone, meter_number, connection_type):
        try:
            cur = self._conn.execute(
                """INSERT INTO customers (name, cnic, address, phone, meter_number, connection_type)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (name, cnic, address, phone, meter_number, connection_type),
            )
            self._conn.commit()
            return cur.lastrowid
        except sqlite3.IntegrityError:
            raise BillingError(f"Meter {meter_number} is already registered.")
        except sqlite3.Error:
            raise BillingError("Could not save the customer.")

    def update_customer(self, customer_id, name, cnic, address, phone, meter_number, connection_type):
        try:
            updated = self._conn.execute(
                """UPDATE customers
                   SET name = ?, cnic = ?, address = ?, phone = ?, meter_number = ?, connection_type = ?
                   WHERE id = ?""",
                (name, cnic, address, phone, meter_number, connection_type, customer_id),
            )
            self._conn.commit()
            if updated.rowcount != 1:
                raise BillingError("Customer was not found.")
        except BillingError:
            raise
        except sqlite3.IntegrityError:
            raise BillingError(f"Meter {meter_number} is already registered.")
        except sqlite3.Error:
            raise BillingError("Could not update the customer.")

    def delete_customer(self, customer_id):
        used = self._conn.execute(
            "SELECT COUNT(*) FROM meter_readings WHERE customer_id = ?", (customer_id,)
        ).fetchone()[0]
        if used:
            raise BillingError("This customer has readings, so the record cannot be deleted.")
        deleted = self._conn.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
        self._conn.commit()
        if deleted.rowcount != 1:
            raise BillingError("Customer was not found.")

    def get_customer(self, customer_id):
        return self._one("SELECT * FROM customers WHERE id = ?", (customer_id,))

    def find_by_meter(self, meter_number):
        return self._one("SELECT * FROM customers WHERE meter_number = ?", (meter_number,))

    def search_customers(self, text):
        if not text:
            return self._all("SELECT * FROM customers ORDER BY name")
        like = f"%{text.strip().lower()}%"
        return self._all(
            """SELECT * FROM customers
               WHERE lower(name) LIKE ? OR lower(cnic) LIKE ? OR lower(meter_number) LIKE ?
                  OR lower(phone) LIKE ?
               ORDER BY name""",
            (like, like, like, like),
        )

    def reading_for_month(self, customer_id, month):
        return self._one(
            "SELECT * FROM meter_readings WHERE customer_id = ? AND month = ?",
            (customer_id, month),
        )

    def next_bill_no(self):
        rows = self._all("SELECT bill_no FROM bills")
        highest = 1000
        for row in rows:
            number = row["bill_no"][3:]
            if row["bill_no"].startswith("EB-") and number.isdigit():
                highest = max(highest, int(number))
        return f"EB-{highest + 1}"

    def save_reading_and_bill(self, customer_id, reading, bill):
        try:
            with self._conn:
                cur = self._conn.execute(
                    """INSERT INTO meter_readings
                       (customer_id, month, previous_reading, current_reading, units)
                       VALUES (?, ?, ?, ?, ?)""",
                    (customer_id, reading.month, reading.previous_reading,
                     reading.current_reading, reading.units),
                )
                self._conn.execute(
                    """INSERT INTO bills (
                        bill_no, customer_id, reading_id, month, units, energy_charge,
                        fixed_charge, tax_amount, surcharge, total, due_date, status, paid_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'unpaid', NULL)""",
                    (bill.bill_no, customer_id, cur.lastrowid, bill.month, reading.units,
                     bill.energy_charge, bill.fixed_charge, bill.tax_amount,
                     bill.surcharge, bill.total, bill.due_date.isoformat()),
                )
        except sqlite3.IntegrityError:
            raise BillingError("This month already has a reading for that meter.")
        except sqlite3.Error:
            raise BillingError("Could not save the reading.")

    def list_bills(self):
        return self._all(
            """SELECT b.*, c.name, c.meter_number, c.connection_type, c.phone
               FROM bills AS b
               JOIN customers AS c ON c.id = b.customer_id
               ORDER BY b.month DESC, b.bill_no DESC"""
        )

    def get_bill(self, bill_no):
        return self._one(
            """SELECT b.*, c.name, c.meter_number, c.connection_type, c.phone
               FROM bills AS b JOIN customers AS c ON c.id = b.customer_id
               WHERE b.bill_no = ?""",
            (bill_no,),
        )

    def mark_bill_paid(self, bill_no, surcharge, total, paid_date):
        try:
            updated = self._conn.execute(
                """UPDATE bills
                   SET status = 'paid', surcharge = ?, total = ?, paid_date = ?
                   WHERE bill_no = ? AND status = 'unpaid'""",
                (surcharge, total, paid_date, bill_no),
            )
            self._conn.commit()
            if updated.rowcount != 1:
                raise BillingError("This bill is already paid or was not found.")
        except BillingError:
            raise
        except sqlite3.Error:
            raise BillingError("Could not mark the bill as paid.")

    def get_tariffs(self):
        rows = self._all("SELECT * FROM tariffs")
        return {row["connection_type"]: row for row in rows}

    def update_tariff(self, connection_type, rates):
        try:
            updated = self._conn.execute(
                """UPDATE tariffs SET slab1_units = ?, slab1_rate = ?, slab2_units = ?,
                   slab2_rate = ?, slab3_rate = ?, fixed_charge = ?, tax_percent = ?
                   WHERE connection_type = ?""",
                (rates["slab1_units"], rates["slab1_rate"], rates["slab2_units"],
                 rates["slab2_rate"], rates["slab3_rate"], rates["fixed_charge"],
                 rates["tax_percent"], connection_type),
            )
            self._conn.commit()
            if updated.rowcount != 1:
                raise BillingError(f"No tariff saved for {connection_type}.")
        except BillingError:
            raise
        except sqlite3.Error:
            raise BillingError("Could not save the tariff.")

    def get_setting(self, key):
        row = self._one("SELECT value FROM settings WHERE key = ?", (key,))
        if row is None:
            raise BillingError(f"Missing setting {key}.")
        return float(row["value"])

    def update_setting(self, key, value):
        try:
            updated = self._conn.execute(
                "UPDATE settings SET value = ? WHERE key = ?", (float(value), key)
            )
            self._conn.commit()
            if updated.rowcount != 1:
                raise BillingError(f"Missing setting {key}.")
        except BillingError:
            raise
        except sqlite3.Error:
            raise BillingError("Could not save settings.")
