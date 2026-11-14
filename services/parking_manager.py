from datetime import datetime

from database.database_manager import DatabaseManager
from models.parking_slot import ParkingSlot
from models.parking_ticket import ParkingTicket
from models.vehicle import Car, Motorcycle, Van, Vehicle
from services.payment_calculator import PaymentCalculator
from utils.exceptions import ParkingError

TIME_FMT = "%Y-%m-%d %H:%M:%S"
TYPES = ("Car", "Motorcycle", "Van")


def clean_reg(value):
    reg = " ".join(str(value or "").strip().upper().split())
    if not (3 <= len(reg) <= 15):
        raise ParkingError("Registration number should be 3 to 15 characters.")
    for ch in reg:
        if not (ch.isalnum() or ch in "- "):
            raise ParkingError("Use only letters, numbers, spaces, and hyphens in the registration.")
    return reg


def clean_owner(value):
    name = " ".join(str(value or "").split())
    if not (3 <= len(name) <= 60):
        raise ParkingError("Owner name should be 3 to 60 characters.")
    for ch in name:
        if not (ch.isalpha() or ch in " .'-"):
            raise ParkingError("Owner name should use letters, not numbers.")
    return name


def to_text(value):
    return value.strftime(TIME_FMT)


def to_time(value):
    if isinstance(value, datetime):
        return value.replace(microsecond=0)
    return datetime.strptime(value, TIME_FMT)


class ParkingManager:
    """Entry, exit, slots, and reports. It uses the database and the fee calculator."""

    def __init__(self, db_path, slot_count=20):
        self._db = DatabaseManager(db_path, slot_count=slot_count)
        # Starting prices match get_hourly_rate() on each subclass.
        self._db.seed_if_empty({
            "Car": Car("TEMP", "Temp").get_hourly_rate(),
            "Motorcycle": Motorcycle("TEMP", "Temp").get_hourly_rate(),
            "Van": Van("TEMP", "Temp").get_hourly_rate(),
        })
        self._fees = PaymentCalculator(self._db.get_rates())

    @property
    def database(self):
        return self._db

    def close(self):
        self._db.close()

    def register_vehicle(self, registration_number, owner_name, vehicle_type, entry_time=None):
        registration_number = clean_reg(registration_number)
        owner_name = clean_owner(owner_name)
        if entry_time is None:
            entry_time = datetime.now().replace(microsecond=0)
        if not isinstance(entry_time, datetime):
            raise ParkingError("Entry time is not valid.")
        entry_time = entry_time.replace(microsecond=0)

        vehicle = Vehicle.create(vehicle_type, registration_number, owner_name)
        existing = self._db.active_by_reg(registration_number)
        if existing:
            raise ParkingError(
                f"{registration_number} is already parked in slot {existing['slot_number']} "
                f"(ticket {existing['ticket_id']})."
            )

        free = self._db.first_free_slot()
        if free is None:
            total = self._db.counts()["total"]
            raise ParkingError(f"The parking area is full. All {total} slots are occupied.")

        slot = ParkingSlot(
            free["slot_number"], free["status"], free["registration_number"],
            free["vehicle_type"], free["ticket_id"],
        )
        ticket_id = self._db.next_ticket_id()
        slot.occupy(vehicle.registration_number, vehicle.get_type(), ticket_id)
        self._db.save_entry(
            vehicle.registration_number, vehicle.owner_name, vehicle.get_type(),
            slot.slot_number, ticket_id, to_text(entry_time),
        )
        ticket = ParkingTicket(
            ticket_id, vehicle.registration_number, vehicle.owner_name,
            vehicle.get_type(), slot.slot_number, entry_time,
        )
        return {"ticket": ticket, "vehicle": vehicle}

    def find_parked(self, query):
        text = "" if query is None else str(query).strip()
        if not text:
            raise ParkingError("Enter a registration number or a ticket ID.")

        row = None
        if text.upper().startswith("CP-"):
            row = self._db.active_by_ticket(text.upper())
        if row is None:
            try:
                reg = clean_reg(text)
            except ParkingError:
                reg = None
            if reg:
                row = self._db.active_by_reg(reg)
        if row is None:
            raise ParkingError(f"No parked vehicle matches '{text}'.")
        return self._ticket_from_row(row)

    def preview_fee(self, ticket, exit_time):
        vehicle = Vehicle.create(ticket.vehicle_type, ticket.registration_number, ticket.owner_name)
        self._fees = PaymentCalculator(self._db.get_rates())
        return self._fees.calculate(vehicle, ticket.entry_time, exit_time.replace(microsecond=0))

    def exit_vehicle(self, query, exit_time=None):
        ticket = self.find_parked(query)
        if exit_time is None:
            exit_time = datetime.now().replace(microsecond=0)
        if not isinstance(exit_time, datetime):
            raise ParkingError("Exit time is not valid.")
        exit_time = exit_time.replace(microsecond=0)

        breakdown = self.preview_fee(ticket, exit_time)
        row = self._db.active_by_ticket(ticket.ticket_id)
        self._db.save_exit(
            row, to_text(exit_time), breakdown["duration_text"],
            breakdown["billable_hours"], breakdown["hourly_rate"], breakdown["total"],
        )
        ticket.close(exit_time, breakdown["total"])
        return {"ticket": ticket, "breakdown": breakdown}

    def get_slots(self):
        return [
            ParkingSlot(row["slot_number"], row["status"], row["registration_number"],
                        row["vehicle_type"], row["ticket_id"])
            for row in self._db.fetch_slots()
        ]

    def get_active_tickets(self):
        return [self._ticket_from_row(row) for row in self._db.active_tickets()]

    def get_rates(self):
        rates = self._db.get_rates()
        self._fees = PaymentCalculator(rates)
        return rates

    def update_hourly_rates(self, rates):
        cleaned = {}
        for vehicle_type in TYPES:
            if vehicle_type not in rates:
                raise ParkingError(f"Missing rate for {vehicle_type}.")
            try:
                rate = float(rates[vehicle_type])
            except (TypeError, ValueError):
                raise ParkingError(f"Rate for {vehicle_type} must be a number.")
            if rate <= 0 or rate > 100000:
                raise ParkingError(f"Rate for {vehicle_type} must be greater than 0.")
            cleaned[vehicle_type] = rate
        self._db.update_rates(cleaned)
        self._fees = PaymentCalculator(self._db.get_rates())
        return self.get_rates()

    def get_history(self, search="", status="All", vehicle_type="All"):
        return [self._history_row(row) for row in self._db.history(search, status, vehicle_type)]

    def get_dashboard(self):
        counts = self._db.counts()
        total = counts["total"]
        occupied = counts["occupied"]
        percent = round((occupied / total) * 100, 1) if total else 0
        return {
            "total_slots": total,
            "available": counts["available"],
            "occupied": occupied,
            "occupancy_percent": percent,
            "parked_count": len(self._db.active_tickets()),
            "total_revenue": counts["revenue"],
            "completed_sessions": counts["completed"],
            "recent": self.get_history()[:6],
            "activity": self.get_active_tickets(),
        }

    def get_report(self):
        counts = self._db.counts()
        visits = self._db.visits_by_type()
        money = self._db.revenue_by_type()
        return {
            "completed_sessions": counts["completed"],
            "total_revenue": counts["revenue"],
            "currently_parked": len(self._db.active_tickets()),
            "visits_by_type": [
                {"vehicle_type": name, "visits": int(visits.get(name, 0))} for name in TYPES
            ],
            "revenue_by_type": [
                {
                    "vehicle_type": name,
                    "revenue": float(money.get(name, {}).get("revenue", 0)),
                    "sessions": int(money.get(name, {}).get("sessions", 0)),
                }
                for name in TYPES
            ],
            "daily_revenue": self._db.daily_revenue(),
        }

    def _ticket_from_row(self, row):
        return ParkingTicket(
            row["ticket_id"], row["registration_number"], row["owner_name"],
            row["vehicle_type"], row["slot_number"], to_time(row["entry_time"]),
            status=row["status"],
        )

    def _history_row(self, row):
        row["entry_time"] = to_time(row["entry_time"])
        if row.get("exit_time"):
            row["exit_time"] = to_time(row["exit_time"])
        return row
