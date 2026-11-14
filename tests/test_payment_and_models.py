"""Fee rules, validation, and the object model behind the 12 main cases."""

from datetime import datetime, timedelta

import pytest

from models.parking_slot import ParkingSlot
from models.parking_ticket import ParkingTicket
from models.vehicle import Car, Motorcycle, Van, Vehicle
from services.payment_calculator import PaymentCalculator
from utils.exceptions import ValidationError, VehicleNotFoundError

START = datetime(2026, 11, 14, 9, 0, 0)
RATES = {"Car": 50, "Motorcycle": 30, "Van": 70}


def calculator():
    return PaymentCalculator(RATES)


def test_partial_hour_rounds_up_and_exact_hour_does_not():
    calc = calculator()
    car = Car("LEA-4521", "Ali Khan")

    one_minute = calc.calculate(car, START, START + timedelta(minutes=1))
    assert one_minute["billable_hours"] == 1
    assert one_minute["total_amount"] == 50

    exact_hour = calc.calculate(car, START, START + timedelta(hours=1))
    assert exact_hour["billable_hours"] == 1
    assert exact_hour["total_amount"] == 50

    just_over = calc.calculate(car, START, START + timedelta(hours=1, minutes=1))
    assert just_over["billable_hours"] == 2
    assert just_over["total_amount"] == 100

    exact_two = calc.calculate(Van("ISB-3003", "Campus Shuttle"), START, START + timedelta(hours=2))
    assert exact_two["billable_hours"] == 2
    assert exact_two["hourly_rate"] == 70
    assert exact_two["total_amount"] == 140

    instant = calc.calculate(Motorcycle("KHI-2002", "Sara Ahmed"), START, START)
    assert instant["billable_hours"] == 1
    assert instant["total_amount"] == 30


def test_exit_before_entry_is_rejected():
    with pytest.raises(ValidationError):
        calculator().billable_hours(START, START - timedelta(minutes=5))


def test_admin_rate_overrides_the_class_default():
    car = Car("LEA-4521", "Ali Khan")
    assert car.get_hourly_rate() == 50
    calc = PaymentCalculator({"Car": 80, "Motorcycle": 30, "Van": 70})
    assert calc.rate_for(car) == 80
    billed = calc.calculate(car, START, START + timedelta(minutes=10))
    assert billed["total_amount"] == 80


def test_missing_rate_falls_back_to_the_subclass():
    car = Car("LEA-4521", "Ali Khan")
    calc = PaymentCalculator({"Motorcycle": 30})
    assert calc.rate_for(car) == 50


def test_subclasses_override_type_rate_and_description():
    vehicles = [
        Vehicle.create("Car", "LEA-4521", "Ali Khan"),
        Vehicle.create("Motorcycle", "KHI-2002", "Sara Ahmed"),
        Vehicle.create("Van", "ISB-3003", "Campus Shuttle"),
    ]
    assert [type(vehicle) for vehicle in vehicles] == [Car, Motorcycle, Van]
    assert [vehicle.get_vehicle_type() for vehicle in vehicles] == ["Car", "Motorcycle", "Van"]
    assert [vehicle.get_hourly_rate() for vehicle in vehicles] == [50, 30, 70]
    descriptions = [vehicle.get_description() for vehicle in vehicles]
    assert len(set(descriptions)) == 3
    for vehicle in vehicles:
        assert isinstance(vehicle, Vehicle)
        assert vehicle.get_vehicle_type() in vehicle.get_description()


def test_unknown_vehicle_type_is_rejected():
    with pytest.raises(ValidationError):
        Vehicle.create("Bus", "LEA-4521", "Ali Khan")


def test_properties_do_not_allow_direct_assignment():
    car = Car("LEA-4521", "Ali Khan")
    with pytest.raises(AttributeError):
        car.registration_number = "OTHER-1"
    assert car.registration_number == "LEA-4521"


def test_slot_cannot_be_occupied_twice():
    slot = ParkingSlot(4)
    slot.occupy("LEA-4521", "Car", "CP-1001")
    with pytest.raises(ValidationError):
        slot.occupy("KHI-2002", "Motorcycle", "CP-1002")
    slot.release()
    assert slot.is_available
    assert slot.registration_number is None


def test_closed_ticket_cannot_be_closed_again():
    ticket = ParkingTicket(
        ticket_id="CP-1001",
        registration_number="LEA-4521",
        owner_name="Ali Khan",
        vehicle_type="Car",
        slot_number=1,
        entry_time=START,
    )
    ticket.close(START, "0s", 1, 50, 50)
    with pytest.raises(ValidationError):
        ticket.close(START, "0s", 1, 50, 50)


def test_empty_and_invalid_fields_are_rejected(manager):
    with pytest.raises(ValidationError):
        manager.register_vehicle("   ", "Ali Khan", "Car")
    with pytest.raises(ValidationError):
        manager.register_vehicle("LEA-4521", "", "Car")
    with pytest.raises(ValidationError):
        manager.register_vehicle("L", "Ali Khan", "Car")
    with pytest.raises(ValidationError):
        manager.register_vehicle("LEA-4521", "A1", "Car")
    assert manager.get_active_tickets() == []


def test_cannot_exit_a_vehicle_that_is_not_parked(manager):
    with pytest.raises(VehicleNotFoundError):
        manager.exit_vehicle("LEA-4521")
    with pytest.raises(ValidationError):
        manager.exit_vehicle("   ")


def test_history_search_and_filters(manager):
    manager.register_vehicle("LEA-4521", "Ali Khan", "Car", entry_time=START)
    manager.register_vehicle("KHI-2002", "Sara Ahmed", "Motorcycle", entry_time=START)
    manager.exit_vehicle("LEA-4521", exit_time=START + timedelta(hours=1))

    assert len(manager.get_history(search="sara")) == 1
    assert len(manager.get_history(search="cp-1001")) == 1
    assert len(manager.get_history(status="Parked")) == 1
    assert len(manager.get_history(status="Completed", vehicle_type="Car")) == 1
    assert manager.get_history(status="Completed", vehicle_type="Van") == []


def test_rate_change_is_used_on_the_next_exit(manager):
    manager.register_vehicle("LEA-4521", "Ali Khan", "Car", entry_time=START)
    manager.update_hourly_rates({"Car": 40, "Motorcycle": 30, "Van": 70})
    result = manager.exit_vehicle("LEA-4521", exit_time=START + timedelta(hours=2))
    assert result["breakdown"]["hourly_rate"] == 40
    assert result["breakdown"]["billable_hours"] == 2
    assert result["breakdown"]["total_amount"] == 80


def test_zero_rate_is_rejected(manager):
    with pytest.raises(ValidationError):
        manager.update_hourly_rates({"Car": 0, "Motorcycle": 30, "Van": 70})
    assert manager.get_rates()["Car"] == 50
