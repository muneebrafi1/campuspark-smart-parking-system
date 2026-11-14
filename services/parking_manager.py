"""The object the pages talk to.

ParkingManager does not write SQL and does not draw buttons.
It keeps a DatabaseManager and a PaymentCalculator and uses both.
That relationship is composition: the manager "has" those helpers.
"""

from datetime import datetime

from database.database_manager import DatabaseManager
from models.parking_slot import ParkingSlot
from models.parking_ticket import ParkingTicket
from models.vehicle import Vehicle
from services.payment_calculator import PaymentCalculator
from utils.exceptions import ValidationError, VehicleNotFoundError
from utils.helpers import (
    DEFAULT_SLOT_COUNT,
    VEHICLE_TYPES,
    format_money,
    format_timestamp,
    normalize_owner_name,
    normalize_registration,
    parse_timestamp,
)


class ParkingManager:
    """Entry, exit, slots, history, prices, and dashboard numbers."""

    def __init__(self, db_path, slot_count=DEFAULT_SLOT_COUNT):
        if slot_count < 1:
            raise ValidationError("The parking area needs at least one slot.")
        self._database = DatabaseManager(db_path, slot_count=slot_count)
        self._database.seed_slots_if_empty()
        self._database.seed_rates_if_empty(Vehicle.default_rates())
        self._calculator = PaymentCalculator(self._database.get_rates())

    @property
    def database(self):
        """The database helper. Useful in tests and in the viva."""
        return self._database

    @property
    def calculator(self):
        """The fee helper currently held by this manager."""
        return self._calculator

    def close(self):
        self._database.close()

    def register_vehicle(self, registration_number, owner_name, vehicle_type, entry_time=None):
        """Check the form, build a Vehicle, and store the visit.

        The first free slot (lowest number) is chosen inside the database
        transaction so two saves cannot take the same slot.
        """
        registration_number = normalize_registration(registration_number)
        owner_name = normalize_owner_name(owner_name)
        if entry_time is None:
            entry_time = datetime.now().replace(microsecond=0)
        if not isinstance(entry_time, datetime):
            raise ValidationError("Entry time must be a valid date and time.")
        entry_time = entry_time.replace(microsecond=0)

        # Vehicle.create returns a Car, Motorcycle, or Van.
        vehicle = Vehicle.create(vehicle_type, registration_number, owner_name)
        row = self._database.create_entry(
            registration_number=vehicle.registration_number,
            owner_name=vehicle.owner_name,
            vehicle_type=vehicle.get_vehicle_type(),
            entry_time=format_timestamp(entry_time),
        )
        ticket = self._ticket_from_row(row)
        return {
            "ticket": ticket,
            "vehicle": vehicle,
            "message": (
                f"{vehicle.get_description()} parked in slot {ticket.slot_number}. "
                f"Ticket {ticket.ticket_id}."
            ),
        }

    def find_parked(self, query):
        """Find an active visit by ticket ID or registration number."""
        text = "" if query is None else str(query).strip()
        if not text:
            raise ValidationError("Enter a registration number or a ticket ID.")

        row = None
        upper = text.upper()
        if upper.startswith("CP-"):
            row = self._database.get_active_by_ticket_id(upper)
        if row is None:
            try:
                registration = normalize_registration(text)
            except ValidationError:
                registration = None
            if registration is not None:
                row = self._database.get_active_by_registration(registration)
        if row is None:
            raise VehicleNotFoundError(
                f"No parked vehicle matches '{text}'. "
                "Check the registration number or ticket ID."
            )
        return self._ticket_from_row(row)

    def preview_fee(self, ticket, exit_time):
        """Calculate a fee without saving. The exit page uses this as a preview."""
        if not isinstance(exit_time, datetime):
            raise ValidationError("Exit time must be a valid date and time.")
        vehicle = Vehicle.create(
            ticket.vehicle_type,
            ticket.registration_number,
            ticket.owner_name,
        )
        calculator = PaymentCalculator(self._database.get_rates())
        return calculator.calculate(vehicle, ticket.entry_time, exit_time.replace(microsecond=0))

    def exit_vehicle(self, query, exit_time=None):
        """Charge the vehicle, save the payment, and free the slot."""
        ticket = self.find_parked(query)
        if exit_time is None:
            exit_time = datetime.now().replace(microsecond=0)
        if not isinstance(exit_time, datetime):
            raise ValidationError("Exit time must be a valid date and time.")
        exit_time = exit_time.replace(microsecond=0)

        breakdown = self.preview_fee(ticket, exit_time)
        self._database.complete_exit(
            ticket_id=ticket.ticket_id,
            exit_time=format_timestamp(exit_time),
            duration_text=breakdown["duration_text"],
            billable_hours=breakdown["billable_hours"],
            hourly_rate=breakdown["hourly_rate"],
            fee=breakdown["total_amount"],
        )
        ticket.close(
            exit_time=exit_time,
            duration_text=breakdown["duration_text"],
            billable_hours=breakdown["billable_hours"],
            hourly_rate=breakdown["hourly_rate"],
            fee=breakdown["total_amount"],
        )
        return {
            "ticket": ticket,
            "breakdown": breakdown,
            "message": (
                f"Exit complete for {ticket.registration_number}. "
                f"Slot {ticket.slot_number} is free. "
                f"Fee is {format_money(breakdown['total_amount'])}."
            ),
        }

    def get_slots(self):
        """ParkingSlot objects in slot-number order."""
        slots = []
        for row in self._database.fetch_slots():
            slots.append(
                ParkingSlot(
                    slot_number=row["slot_number"],
                    status=row["status"],
                    registration_number=row["registration_number"],
                    vehicle_type=row["vehicle_type"],
                    ticket_id=row["ticket_id"],
                )
            )
        return slots

    def get_active_tickets(self):
        return [self._ticket_from_row(row) for row in self._database.get_active_tickets()]

    def get_rates(self):
        rates = self._database.get_rates()
        self._calculator = PaymentCalculator(rates)
        return rates

    def update_hourly_rates(self, rates):
        """Save new prices. The next exit uses these numbers."""
        if not isinstance(rates, dict):
            raise ValidationError("Pricing must include each vehicle type.")
        cleaned = {}
        for vehicle_type in VEHICLE_TYPES:
            if vehicle_type not in rates:
                raise ValidationError(f"Missing hourly rate for {vehicle_type}.")
            try:
                rate = float(rates[vehicle_type])
            except (TypeError, ValueError):
                raise ValidationError(f"Hourly rate for {vehicle_type} must be a number.")
            if rate <= 0 or rate > 100000:
                raise ValidationError(
                    f"Hourly rate for {vehicle_type} must be greater than 0 and at most 100000."
                )
            cleaned[vehicle_type] = rate
        self._database.update_rates(cleaned)
        self._calculator = PaymentCalculator(self._database.get_rates())
        return self.get_rates()

    def get_history(self, search="", status="All", vehicle_type="All"):
        return [self._history_record(row) for row in self._database.get_history(search, status, vehicle_type)]

    def get_dashboard(self):
        """Numbers for the home page. All of them come from the database."""
        total = self._database.count_slots()
        occupied = self._database.count_occupied_slots()
        available = total - occupied
        percent = round((occupied / total) * 100, 1) if total else 0.0
        return {
            "total_slots": total,
            "available": available,
            "occupied": occupied,
            "occupancy_percent": percent,
            "parked_count": len(self._database.get_active_tickets()),
            "total_revenue": self._database.total_revenue(),
            "completed_sessions": self._database.count_transactions(),
            "recent": [
                self._history_record(row) for row in self._database.get_recent_entries(limit=6)
            ],
            "activity": self.get_active_tickets(),
        }

    def get_report(self):
        """Figures and series for the reports page."""
        visits = self._database.visits_by_type()
        revenue = self._database.revenue_by_type()
        return {
            "completed_sessions": self._database.count_transactions(),
            "total_revenue": self._database.total_revenue(),
            "currently_parked": len(self._database.get_active_tickets()),
            "visits_by_type": [
                {"vehicle_type": name, "visits": int(visits.get(name, 0))}
                for name in VEHICLE_TYPES
            ],
            "revenue_by_type": [
                {
                    "vehicle_type": name,
                    "revenue": float(revenue.get(name, {}).get("revenue", 0)),
                    "sessions": int(revenue.get(name, {}).get("sessions", 0)),
                }
                for name in VEHICLE_TYPES
            ],
            "daily_revenue": self._database.daily_revenue(),
        }

    def _ticket_from_row(self, row):
        return ParkingTicket(
            ticket_id=row["ticket_id"],
            registration_number=row["registration_number"],
            owner_name=row["owner_name"],
            vehicle_type=row["vehicle_type"],
            slot_number=row["slot_number"],
            entry_time=parse_timestamp(row["entry_time"]),
            status=row["status"],
        )

    def _history_record(self, row):
        return {
            "ticket_id": row["ticket_id"],
            "registration_number": row["registration_number"],
            "owner_name": row["owner_name"],
            "vehicle_type": row["vehicle_type"],
            "slot_number": row["slot_number"],
            "entry_time": parse_timestamp(row["entry_time"]),
            "exit_time": parse_timestamp(row["exit_time"]) if row.get("exit_time") else None,
            "duration_text": row.get("duration_text"),
            "billable_hours": row.get("billable_hours"),
            "hourly_rate": row.get("hourly_rate"),
            "fee": row.get("fee"),
            "status": row["status"],
        }
