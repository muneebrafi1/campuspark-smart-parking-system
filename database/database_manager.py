"""All SQL for CampusPark lives in this class.

Other files never call sqlite3. They ask DatabaseManager for rows.
Every user value is passed with a ? placeholder, not pasted into the
SQL text.
"""

import sqlite3
from pathlib import Path

from models.parking_slot import ParkingSlot
from utils.exceptions import (
    DatabaseError,
    DuplicateVehicleError,
    ParkingFullError,
    ValidationError,
    VehicleNotFoundError,
)
from utils.helpers import DEFAULT_SLOT_COUNT


class DatabaseManager:
    """Opens the SQLite file, creates tables, and runs queries."""

    def __init__(self, db_path, slot_count=DEFAULT_SLOT_COUNT):
        self._db_path = str(db_path)
        self._slot_count = slot_count
        self._connection = None
        self._connect()
        self._create_tables()

    @property
    def db_path(self):
        return self._db_path

    def close(self):
        """Close the file. The next DatabaseManager can open it again."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def _connect(self):
        try:
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(
                self._db_path,
                timeout=10,
                check_same_thread=False,
            )
            self._connection.row_factory = sqlite3.Row
            # Foreign keys are off unless we turn them on for this connection.
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.execute("PRAGMA journal_mode = WAL")
        except sqlite3.Error as exc:
            raise DatabaseError(
                "Could not open the parking database. "
                "Check that the data folder is writable."
            ) from exc

    def _create_tables(self):
        """Create empty tables. Safe to call every time the app starts."""
        try:
            self._connection.executescript(
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
                    status TEXT NOT NULL CHECK (status IN ('available', 'occupied')),
                    registration_number TEXT,
                    vehicle_type TEXT,
                    ticket_id TEXT
                );

                CREATE TABLE IF NOT EXISTS parking_tickets (
                    ticket_id TEXT PRIMARY KEY,
                    vehicle_id INTEGER NOT NULL,
                    registration_number TEXT NOT NULL,
                    owner_name TEXT NOT NULL,
                    vehicle_type TEXT NOT NULL,
                    slot_number INTEGER NOT NULL,
                    entry_time TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('parked', 'completed')),
                    FOREIGN KEY (vehicle_id) REFERENCES vehicles (id),
                    FOREIGN KEY (slot_number) REFERENCES parking_slots (slot_number)
                );

                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id TEXT NOT NULL UNIQUE,
                    registration_number TEXT NOT NULL,
                    owner_name TEXT NOT NULL,
                    vehicle_type TEXT NOT NULL,
                    slot_number INTEGER NOT NULL,
                    entry_time TEXT NOT NULL,
                    exit_time TEXT NOT NULL,
                    duration_text TEXT NOT NULL,
                    billable_hours INTEGER NOT NULL,
                    hourly_rate REAL NOT NULL,
                    fee REAL NOT NULL,
                    status TEXT NOT NULL DEFAULT 'completed'
                );

                CREATE TABLE IF NOT EXISTS pricing (
                    vehicle_type TEXT PRIMARY KEY,
                    hourly_rate REAL NOT NULL CHECK (hourly_rate > 0)
                );

                -- Only one active visit per registration. Completed visits stay.
                CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_registration
                ON parking_tickets (registration_number)
                WHERE status = 'parked';
                """
            )
            self._connection.commit()
        except sqlite3.Error as exc:
            raise DatabaseError("Could not create the database tables.") from exc

    def seed_slots_if_empty(self):
        """Add slots 1..N the first time, and leave them alone after that."""
        try:
            total = self.count_slots()
            if total == 0:
                numbers = [(number,) for number in range(1, self._slot_count + 1)]
                self._connection.executemany(
                    """
                    INSERT INTO parking_slots (
                        slot_number, status, registration_number, vehicle_type, ticket_id
                    ) VALUES (?, 'available', NULL, NULL, NULL)
                    """,
                    numbers,
                )
                self._connection.commit()
        except sqlite3.Error as exc:
            raise DatabaseError("Could not create the parking slots.") from exc

    def seed_rates_if_empty(self, rates):
        """Save starting prices only when the pricing table is empty."""
        try:
            existing = self._connection.execute(
                "SELECT COUNT(*) AS total FROM pricing"
            ).fetchone()["total"]
            if existing == 0:
                rows = [(vehicle_type, float(rate)) for vehicle_type, rate in rates.items()]
                self._connection.executemany(
                    "INSERT INTO pricing (vehicle_type, hourly_rate) VALUES (?, ?)",
                    rows,
                )
                self._connection.commit()
        except sqlite3.Error as exc:
            raise DatabaseError("Could not save the default prices.") from exc

    def _next_ticket_id(self):
        """Next ID such as CP-1001. Looks at tickets and payments."""
        rows = self._connection.execute(
            """
            SELECT ticket_id FROM parking_tickets
            UNION
            SELECT ticket_id FROM transactions
            """
        ).fetchall()
        highest = 1000
        for row in rows:
            ticket_id = row["ticket_id"]
            if ticket_id.startswith("CP-") and ticket_id[3:].isdigit():
                highest = max(highest, int(ticket_id[3:]))
        return f"CP-{highest + 1}"

    def create_entry(self, registration_number, owner_name, vehicle_type, entry_time):
        """Save a vehicle, take the first free slot, and open a ticket.

        The whole save is one transaction. If any step fails, nothing is kept.
        """
        try:
            with self._connection:
                existing = self._connection.execute(
                    """
                    SELECT ticket_id, slot_number
                    FROM parking_tickets
                    WHERE registration_number = ? AND status = 'parked'
                    """,
                    (registration_number,),
                ).fetchone()
                if existing is not None:
                    raise DuplicateVehicleError(
                        f"{registration_number} is already parked in slot "
                        f"{existing['slot_number']} (ticket {existing['ticket_id']}). "
                        "Exit that visit before parking it again."
                    )

                slot_row = self._connection.execute(
                    """
                    SELECT slot_number, status, registration_number, vehicle_type, ticket_id
                    FROM parking_slots
                    WHERE status = 'available'
                    ORDER BY slot_number
                    LIMIT 1
                    """
                ).fetchone()
                if slot_row is None:
                    total = self._connection.execute(
                        "SELECT COUNT(*) AS total FROM parking_slots"
                    ).fetchone()["total"]
                    raise ParkingFullError(
                        f"The parking area is full. All {total} slots are occupied."
                    )

                ticket_id = self._next_ticket_id()
                # ParkingSlot.occupy refuses a slot that is already taken.
                slot = ParkingSlot(
                    slot_number=slot_row["slot_number"],
                    status=slot_row["status"],
                    registration_number=slot_row["registration_number"],
                    vehicle_type=slot_row["vehicle_type"],
                    ticket_id=slot_row["ticket_id"],
                )
                slot.occupy(registration_number, vehicle_type, ticket_id)

                created = self._connection.execute(
                    """
                    INSERT INTO vehicles (
                        registration_number, owner_name, vehicle_type, created_at
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (registration_number, owner_name, vehicle_type, entry_time),
                )
                self._connection.execute(
                    """
                    INSERT INTO parking_tickets (
                        ticket_id, vehicle_id, registration_number, owner_name,
                        vehicle_type, slot_number, entry_time, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'parked')
                    """,
                    (
                        ticket_id,
                        created.lastrowid,
                        registration_number,
                        owner_name,
                        vehicle_type,
                        slot.slot_number,
                        entry_time,
                    ),
                )
                updated = self._connection.execute(
                    """
                    UPDATE parking_slots
                    SET status = ?,
                        registration_number = ?,
                        vehicle_type = ?,
                        ticket_id = ?
                    WHERE slot_number = ? AND status = 'available'
                    """,
                    (
                        slot.status,
                        slot.registration_number,
                        slot.vehicle_type,
                        slot.ticket_id,
                        slot.slot_number,
                    ),
                )
                if updated.rowcount != 1:
                    raise DatabaseError("Could not assign a parking slot.")
            return self.get_ticket(ticket_id)
        except (DuplicateVehicleError, ParkingFullError, ValidationError, DatabaseError):
            raise
        except sqlite3.IntegrityError as exc:
            raise DuplicateVehicleError(
                f"{registration_number} is already parked. "
                "Exit that visit before parking it again."
            ) from exc
        except sqlite3.Error as exc:
            raise DatabaseError("Could not save the vehicle entry.") from exc

    def complete_exit(
        self,
        ticket_id,
        exit_time,
        duration_text,
        billable_hours,
        hourly_rate,
        fee,
    ):
        """Close the ticket, store the payment, and free the slot."""
        try:
            with self._connection:
                ticket = self._connection.execute(
                    """
                    SELECT *
                    FROM parking_tickets
                    WHERE ticket_id = ? AND status = 'parked'
                    """,
                    (ticket_id,),
                ).fetchone()
                if ticket is None:
                    raise VehicleNotFoundError("This visit is no longer active.")

                slot_row = self._connection.execute(
                    """
                    SELECT slot_number, status, registration_number, vehicle_type, ticket_id
                    FROM parking_slots
                    WHERE slot_number = ?
                    """,
                    (ticket["slot_number"],),
                ).fetchone()
                if slot_row is None or slot_row["ticket_id"] != ticket_id:
                    raise ValidationError(
                        f"Slot {ticket['slot_number']} is not assigned to ticket {ticket_id}."
                    )

                slot = ParkingSlot(
                    slot_number=slot_row["slot_number"],
                    status=slot_row["status"],
                    registration_number=slot_row["registration_number"],
                    vehicle_type=slot_row["vehicle_type"],
                    ticket_id=slot_row["ticket_id"],
                )
                slot.release()

                closed = self._connection.execute(
                    """
                    UPDATE parking_tickets
                    SET status = 'completed'
                    WHERE ticket_id = ? AND status = 'parked'
                    """,
                    (ticket_id,),
                )
                if closed.rowcount != 1:
                    raise DatabaseError("Could not close the ticket.")

                self._connection.execute(
                    """
                    INSERT INTO transactions (
                        ticket_id, registration_number, owner_name, vehicle_type,
                        slot_number, entry_time, exit_time, duration_text,
                        billable_hours, hourly_rate, fee, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'completed')
                    """,
                    (
                        ticket["ticket_id"],
                        ticket["registration_number"],
                        ticket["owner_name"],
                        ticket["vehicle_type"],
                        ticket["slot_number"],
                        ticket["entry_time"],
                        exit_time,
                        duration_text,
                        billable_hours,
                        hourly_rate,
                        fee,
                    ),
                )
                freed = self._connection.execute(
                    """
                    UPDATE parking_slots
                    SET status = ?,
                        registration_number = ?,
                        vehicle_type = ?,
                        ticket_id = ?
                    WHERE slot_number = ?
                    """,
                    (
                        slot.status,
                        slot.registration_number,
                        slot.vehicle_type,
                        slot.ticket_id,
                        slot.slot_number,
                    ),
                )
                if freed.rowcount != 1:
                    raise DatabaseError("Could not release the parking slot.")
            return self.get_transaction(ticket_id)
        except (VehicleNotFoundError, ValidationError, DatabaseError):
            raise
        except sqlite3.Error as exc:
            raise DatabaseError("Could not complete the exit.") from exc

    def get_ticket(self, ticket_id):
        row = self._connection.execute(
            "SELECT * FROM parking_tickets WHERE ticket_id = ?",
            (ticket_id,),
        ).fetchone()
        return dict(row) if row else None

    def get_transaction(self, ticket_id):
        row = self._connection.execute(
            "SELECT * FROM transactions WHERE ticket_id = ?",
            (ticket_id,),
        ).fetchone()
        return dict(row) if row else None

    def get_active_by_registration(self, registration_number):
        row = self._connection.execute(
            """
            SELECT * FROM parking_tickets
            WHERE registration_number = ? AND status = 'parked'
            """,
            (registration_number,),
        ).fetchone()
        return dict(row) if row else None

    def get_active_by_ticket_id(self, ticket_id):
        row = self._connection.execute(
            """
            SELECT * FROM parking_tickets
            WHERE ticket_id = ? AND status = 'parked'
            """,
            (ticket_id,),
        ).fetchone()
        return dict(row) if row else None

    def get_active_tickets(self):
        rows = self._connection.execute(
            """
            SELECT * FROM parking_tickets
            WHERE status = 'parked'
            ORDER BY slot_number
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def fetch_slots(self):
        rows = self._connection.execute(
            """
            SELECT slot_number, status, registration_number, vehicle_type, ticket_id
            FROM parking_slots
            ORDER BY slot_number
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def count_slots(self):
        return self._connection.execute(
            "SELECT COUNT(*) AS total FROM parking_slots"
        ).fetchone()["total"]

    def count_occupied_slots(self):
        return self._connection.execute(
            "SELECT COUNT(*) AS total FROM parking_slots WHERE status = 'occupied'"
        ).fetchone()["total"]

    def count_transactions(self):
        return self._connection.execute(
            "SELECT COUNT(*) AS total FROM transactions"
        ).fetchone()["total"]

    def total_revenue(self):
        value = self._connection.execute(
            "SELECT COALESCE(SUM(fee), 0) AS revenue FROM transactions"
        ).fetchone()["revenue"]
        return float(value)

    def get_rates(self):
        rows = self._connection.execute(
            "SELECT vehicle_type, hourly_rate FROM pricing ORDER BY vehicle_type"
        ).fetchall()
        return {row["vehicle_type"]: float(row["hourly_rate"]) for row in rows}

    def update_rates(self, rates):
        """Replace the saved hourly prices in one transaction."""
        try:
            with self._connection:
                for vehicle_type, rate in rates.items():
                    updated = self._connection.execute(
                        """
                        UPDATE pricing
                        SET hourly_rate = ?
                        WHERE vehicle_type = ?
                        """,
                        (float(rate), vehicle_type),
                    )
                    if updated.rowcount != 1:
                        raise DatabaseError(f"No saved price for {vehicle_type}.")
        except DatabaseError:
            raise
        except sqlite3.Error as exc:
            raise DatabaseError("Could not update pricing.") from exc

    def get_history(self, search="", status="All", vehicle_type="All"):
        """Tickets on the left, payment on the right. One row per visit."""
        sql = """
            SELECT
                t.ticket_id,
                t.registration_number,
                t.owner_name,
                t.vehicle_type,
                t.slot_number,
                t.entry_time,
                t.status,
                tr.exit_time,
                tr.duration_text,
                tr.billable_hours,
                tr.hourly_rate,
                tr.fee
            FROM parking_tickets AS t
            LEFT JOIN transactions AS tr ON tr.ticket_id = t.ticket_id
            WHERE 1 = 1
        """
        params = []
        if status in ("Parked", "parked"):
            sql += " AND t.status = ?"
            params.append("parked")
        elif status in ("Completed", "completed"):
            sql += " AND t.status = ?"
            params.append("completed")
        if vehicle_type in ("Car", "Motorcycle", "Van"):
            sql += " AND t.vehicle_type = ?"
            params.append(vehicle_type)
        if search and str(search).strip():
            sql += """
                AND (
                    UPPER(t.ticket_id) LIKE ?
                    OR UPPER(t.registration_number) LIKE ?
                    OR UPPER(t.owner_name) LIKE ?
                )
            """
            like = f"%{str(search).strip().upper()}%"
            params.extend([like, like, like])
        sql += " ORDER BY t.entry_time DESC, t.ticket_id DESC"
        rows = self._connection.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def get_recent_entries(self, limit=6):
        rows = self._connection.execute(
            """
            SELECT
                t.ticket_id,
                t.registration_number,
                t.owner_name,
                t.vehicle_type,
                t.slot_number,
                t.entry_time,
                t.status,
                tr.exit_time,
                tr.duration_text,
                tr.billable_hours,
                tr.hourly_rate,
                tr.fee
            FROM parking_tickets AS t
            LEFT JOIN transactions AS tr ON tr.ticket_id = t.ticket_id
            ORDER BY t.entry_time DESC, t.ticket_id DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
        return [dict(row) for row in rows]

    def visits_by_type(self):
        rows = self._connection.execute(
            """
            SELECT vehicle_type, COUNT(*) AS visits
            FROM parking_tickets
            GROUP BY vehicle_type
            """
        ).fetchall()
        return {row["vehicle_type"]: row["visits"] for row in rows}

    def revenue_by_type(self):
        rows = self._connection.execute(
            """
            SELECT vehicle_type, SUM(fee) AS revenue, COUNT(*) AS sessions
            FROM transactions
            GROUP BY vehicle_type
            """
        ).fetchall()
        return {
            row["vehicle_type"]: {
                "revenue": float(row["revenue"]),
                "sessions": row["sessions"],
            }
            for row in rows
        }

    def daily_revenue(self):
        rows = self._connection.execute(
            """
            SELECT substr(exit_time, 1, 10) AS day,
                   SUM(fee) AS revenue,
                   COUNT(*) AS sessions
            FROM transactions
            GROUP BY day
            ORDER BY day
            """
        ).fetchall()
        return [
            {
                "day": row["day"],
                "revenue": float(row["revenue"]),
                "sessions": row["sessions"],
            }
            for row in rows
        ]
