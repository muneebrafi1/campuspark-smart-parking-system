"""Domain objects: vehicles, slots, and tickets."""

from models.parking_slot import ParkingSlot
from models.parking_ticket import ParkingTicket
from models.vehicle import Car, Motorcycle, Van, Vehicle

__all__ = [
    "Vehicle",
    "Car",
    "Motorcycle",
    "Van",
    "ParkingSlot",
    "ParkingTicket",
]
