import sqlite3
from pathlib import Path

from utils.exceptions import ParkingError


class DatabaseManager:
    """Every SQL statement in the project is in this class."""

    def __init__(self, db_path, slot_count=20):
        self._db_path = str(db_path)
        self._slot_count = slot_count
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, timeout=10, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
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
        # One row per arrival, one row per slot, one ticket per visit, one payment on exit.
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS vehicles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                registration_number TEXT NOT NULL,
                owner_name TEXT NOT NULL,
                vehicle_type TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS parking_slots (
                slot_number INTEGER PRIMARY KEY,
                status TEXT NOT NULL,
                registration_number TEXT,
                vehicle_type TEXT,
                ticket_id TEXT
            );
            CREATE TABLE IF NOT EXISTS parking_tickets (
                ticket_id TEXT PRIMARY KEY,
                registration_number TEXT NOT NULL,
                owner_name TEXT NOT NULL,
                vehicle_type TEXT NOT NULL,
                slot_number INTEGER NOT NULL,
                entry_time TEXT NOT NULL,
                status TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS transactions (
                ticket_id TEXT PRIMARY KEY,
                registration_number TEXT NOT NULL,
                owner_name TEXT NOT NULL,
                vehicle_type TEXT NOT NULL,
                slot_number INTEGER NOT NULL,
                entry_time TEXT NOT NULL,
                exit_time TEXT NOT NULL,
                duration_text TEXT NOT NULL,
                billable_hours INTEGER NOT NULL,
                hourly_rate REAL NOT NULL,
                fee REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS pricing (
                vehicle_type TEXT PRIMARY KEY,
                hourly_rate REAL NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS one_active_reg
            ON parking_tickets (registration_number) WHERE status = 'parked';
            """
        )
        self._conn.commit()

    def seed_if_empty(self, rates):
        if self._conn.execute("SELECT COUNT(*) FROM parking_slots").fetchone()[0] == 0:
            self._conn.executemany(
                "INSERT INTO parking_slots (slot_number, status) VALUES (?, 'available')",
                [(n,) for n in range(1, self._slot_count + 1)],
            )
        if self._conn.execute("SELECT COUNT(*) FROM pricing").fetchone()[0] == 0:
            self._conn.executemany(
                "INSERT INTO pricing (vehicle_type, hourly_rate) VALUES (?, ?)",
                list(rates.items()),
            )
        self._conn.commit()

    def next_ticket_id(self):
        rows = self._all(
            "SELECT ticket_id FROM parking_tickets UNION SELECT ticket_id FROM transactions"
        )
        highest = 1000
        for row in rows:
            number = row["ticket_id"][3:]
            if row["ticket_id"].startswith("CP-") and number.isdigit():
                highest = max(highest, int(number))
        return f"CP-{highest + 1}"

    def active_by_reg(self, registration_number):
        return self._one(
            "SELECT * FROM parking_tickets WHERE registration_number = ? AND status = 'parked'",
            (registration_number,),
        )

    def active_by_ticket(self, ticket_id):
        return self._one(
            "SELECT * FROM parking_tickets WHERE ticket_id = ? AND status = 'parked'",
            (ticket_id,),
        )

    def first_free_slot(self):
        return self._one(
            "SELECT * FROM parking_slots WHERE status = 'available' ORDER BY slot_number LIMIT 1"
        )

    def fetch_slots(self):
        return self._all("SELECT * FROM parking_slots ORDER BY slot_number")

    def active_tickets(self):
        return self._all(
            "SELECT * FROM parking_tickets WHERE status = 'parked' ORDER BY slot_number"
        )

    def save_entry(self, registration_number, owner_name, vehicle_type, slot_number, ticket_id, entry_time):
        try:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO vehicles (registration_number, owner_name, vehicle_type, created_at) VALUES (?, ?, ?, ?)",
                    (registration_number, owner_name, vehicle_type, entry_time),
                )
                self._conn.execute(
                    """INSERT INTO parking_tickets
                       (ticket_id, registration_number, owner_name, vehicle_type, slot_number, entry_time, status)
                       VALUES (?, ?, ?, ?, ?, ?, 'parked')""",
                    (ticket_id, registration_number, owner_name, vehicle_type, slot_number, entry_time),
                )
                updated = self._conn.execute(
                    """UPDATE parking_slots
                       SET status = 'occupied', registration_number = ?, vehicle_type = ?, ticket_id = ?
                       WHERE slot_number = ? AND status = 'available'""",
                    (registration_number, vehicle_type, ticket_id, slot_number),
                )
                if updated.rowcount != 1:
                    raise ParkingError("Could not assign that slot.")
        except ParkingError:
            raise
        except sqlite3.IntegrityError:
            raise ParkingError(f"{registration_number} is already parked.")
        except sqlite3.Error:
            raise ParkingError("Could not save the entry. Please try again.")

    def save_exit(self, ticket, exit_time, duration_text, billable_hours, hourly_rate, fee):
        try:
            with self._conn:
                closed = self._conn.execute(
                    "UPDATE parking_tickets SET status = 'completed' WHERE ticket_id = ? AND status = 'parked'",
                    (ticket["ticket_id"],),
                )
                if closed.rowcount != 1:
                    raise ParkingError("This visit is no longer active.")
                self._conn.execute(
                    """INSERT INTO transactions (
                        ticket_id, registration_number, owner_name, vehicle_type, slot_number,
                        entry_time, exit_time, duration_text, billable_hours, hourly_rate, fee
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        ticket["ticket_id"], ticket["registration_number"], ticket["owner_name"],
                        ticket["vehicle_type"], ticket["slot_number"], ticket["entry_time"],
                        exit_time, duration_text, billable_hours, hourly_rate, fee,
                    ),
                )
                freed = self._conn.execute(
                    """UPDATE parking_slots
                       SET status = 'available', registration_number = NULL, vehicle_type = NULL, ticket_id = NULL
                       WHERE slot_number = ? AND ticket_id = ?""",
                    (ticket["slot_number"], ticket["ticket_id"]),
                )
                if freed.rowcount != 1:
                    raise ParkingError("Could not free the slot for this ticket.")
        except ParkingError:
            raise
        except sqlite3.Error:
            raise ParkingError("Could not save the exit. Please try again.")

    def get_transaction(self, ticket_id):
        return self._one("SELECT * FROM transactions WHERE ticket_id = ?", (ticket_id,))

    def get_rates(self):
        rows = self._all("SELECT vehicle_type, hourly_rate FROM pricing")
        return {row["vehicle_type"]: float(row["hourly_rate"]) for row in rows}

    def update_rates(self, rates):
        try:
            with self._conn:
                for vehicle_type, rate in rates.items():
                    updated = self._conn.execute(
                        "UPDATE pricing SET hourly_rate = ? WHERE vehicle_type = ?",
                        (float(rate), vehicle_type),
                    )
                    if updated.rowcount != 1:
                        raise ParkingError(f"No saved price for {vehicle_type}.")
        except ParkingError:
            raise
        except sqlite3.Error:
            raise ParkingError("Could not update the prices.")

    def history(self, search="", status="All", vehicle_type="All"):
        sql = """
            SELECT t.ticket_id, t.registration_number, t.owner_name, t.vehicle_type,
                   t.slot_number, t.entry_time, t.status,
                   tr.exit_time, tr.duration_text, tr.billable_hours, tr.hourly_rate, tr.fee
            FROM parking_tickets AS t
            LEFT JOIN transactions AS tr ON tr.ticket_id = t.ticket_id
            WHERE 1 = 1
        """
        params = []
        if status in ("Parked", "Completed"):
            sql += " AND t.status = ?"
            params.append(status.lower())
        if vehicle_type in ("Car", "Motorcycle", "Van"):
            sql += " AND t.vehicle_type = ?"
            params.append(vehicle_type)
        if search and str(search).strip():
            like = f"%{str(search).strip().upper()}%"
            sql += " AND (UPPER(t.ticket_id) LIKE ? OR UPPER(t.registration_number) LIKE ? OR UPPER(t.owner_name) LIKE ?)"
            params.extend([like, like, like])
        sql += " ORDER BY t.entry_time DESC, t.ticket_id DESC"
        return self._all(sql, params)

    def counts(self):
        total = self._conn.execute("SELECT COUNT(*) FROM parking_slots").fetchone()[0]
        occupied = self._conn.execute(
            "SELECT COUNT(*) FROM parking_slots WHERE status = 'occupied'"
        ).fetchone()[0]
        completed = self._conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        revenue = self._conn.execute("SELECT COALESCE(SUM(fee), 0) FROM transactions").fetchone()[0]
        return {
            "total": total,
            "occupied": occupied,
            "available": total - occupied,
            "completed": completed,
            "revenue": float(revenue),
        }

    def visits_by_type(self):
        rows = self._all("SELECT vehicle_type, COUNT(*) AS visits FROM parking_tickets GROUP BY vehicle_type")
        return {row["vehicle_type"]: row["visits"] for row in rows}

    def revenue_by_type(self):
        rows = self._all(
            "SELECT vehicle_type, SUM(fee) AS revenue, COUNT(*) AS sessions FROM transactions GROUP BY vehicle_type"
        )
        return {
            row["vehicle_type"]: {"revenue": float(row["revenue"]), "sessions": row["sessions"]}
            for row in rows
        }

    def daily_revenue(self):
        rows = self._all(
            "SELECT substr(exit_time, 1, 10) AS day, SUM(fee) AS revenue FROM transactions GROUP BY day ORDER BY day"
        )
        return [{"day": row["day"], "revenue": float(row["revenue"])} for row in rows]
