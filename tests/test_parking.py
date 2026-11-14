"""The 12 checks from the project brief. Each test uses its own database file."""

from datetime import datetime, timedelta

import pytest

from database.database_manager import DatabaseManager
from models.vehicle import Car, Motorcycle
from services.parking_manager import ParkingManager
from utils.exceptions import ParkingError

START = datetime(2026, 11, 14, 9, 0, 0)


def test_01_register_new_vehicle(manager):
    result = manager.register_vehicle("lea-4521", "  Ali   Khan ", "car", entry_time=START)
    ticket = result["ticket"]
    assert isinstance(result["vehicle"], Car)
    assert ticket.registration_number == "LEA-4521"
    assert ticket.owner_name == "Ali Khan"
    assert ticket.vehicle_type == "Car"
    assert ticket.status == "parked"
    assert ticket.ticket_id == "CP-1001"
    assert ticket.entry_time == START


def test_02_auto_allocate_first_free_slot(manager):
    result = manager.register_vehicle("LEA-4521", "Ali Khan", "Car", entry_time=START)
    assert result["ticket"].slot_number == 1
    slots = manager.get_slots()
    assert slots[0].is_occupied
    assert slots[0].registration_number == "LEA-4521"
    assert all(slot.is_available for slot in slots[1:])


def test_03_register_another_vehicle(manager):
    first = manager.register_vehicle("LEA-4521", "Ali Khan", "Car", entry_time=START)
    second = manager.register_vehicle("khi-2002", "Sara Ahmed", "motorcycle", entry_time=START)
    assert isinstance(second["vehicle"], Motorcycle)
    assert second["ticket"].ticket_id == "CP-1002"
    assert second["ticket"].slot_number == 2
    assert second["ticket"].slot_number != first["ticket"].slot_number


def test_04_occupied_slots_update(manager):
    manager.register_vehicle("LEA-4521", "Ali Khan", "Car", entry_time=START)
    manager.register_vehicle("KHI-2002", "Sara Ahmed", "Motorcycle", entry_time=START)
    slots = manager.get_slots()
    assert sum(slot.is_occupied for slot in slots) == 2
    assert slots[0].vehicle_type == "Car"
    assert slots[1].registration_number == "KHI-2002"
    assert slots[2].is_available
    assert manager.get_dashboard()["occupied"] == 2
    assert manager.get_dashboard()["available"] == 18


def test_05_duplicate_parked_vehicle_rejected(manager):
    manager.register_vehicle("LEA-4521", "Ali Khan", "Car", entry_time=START)
    with pytest.raises(ParkingError, match="already parked"):
        manager.register_vehicle("lea-4521", "Someone Else", "Van", entry_time=START)
    assert len(manager.get_active_tickets()) == 1


def test_06_parking_full_rejected(manager):
    owners = ("Ali Khan", "Sara Ahmed", "Campus Shuttle")
    kinds = ("Car", "Motorcycle", "Van")
    for number in range(20):
        manager.register_vehicle(
            f"PK-{1000 + number}",
            owners[number % 3],
            kinds[number % 3],
            entry_time=START,
        )
    with pytest.raises(ParkingError, match="full"):
        manager.register_vehicle("PK-9999", "Ali Khan", "Car", entry_time=START)
    assert manager.get_dashboard()["occupied"] == 20
    assert len(manager.get_active_tickets()) == 20


def test_07_exit_vehicle(manager):
    manager.register_vehicle("LEA-4521", "Ali Khan", "Car", entry_time=START)
    result = manager.exit_vehicle("CP-1001", exit_time=START + timedelta(hours=2))
    assert result["ticket"].status == "completed"
    assert result["ticket"].fee == 100
    assert manager.get_active_tickets() == []
    with pytest.raises(ParkingError):
        manager.find_parked("LEA-4521")


def test_08_fee_minimum_one_hour_and_round_up(manager):
    manager.register_vehicle("LEA-4521", "Ali Khan", "Car", entry_time=START)
    partial = manager.exit_vehicle("LEA-4521", exit_time=START + timedelta(hours=1, minutes=20))
    assert partial["breakdown"]["duration_text"] == "1h 20m"
    assert partial["breakdown"]["billable_hours"] == 2
    assert partial["breakdown"]["hourly_rate"] == 50
    assert partial["breakdown"]["total"] == 100

    manager.register_vehicle("KHI-2002", "Sara Ahmed", "Motorcycle", entry_time=START)
    short = manager.exit_vehicle("KHI-2002", exit_time=START + timedelta(minutes=20))
    assert short["breakdown"]["billable_hours"] == 1
    assert short["breakdown"]["total"] == 30

    manager.register_vehicle("ISB-3003", "Campus Shuttle", "Van", entry_time=START)
    exact = manager.exit_vehicle("ISB-3003", exit_time=START + timedelta(hours=3))
    assert exact["breakdown"]["billable_hours"] == 3
    assert exact["breakdown"]["total"] == 210


def test_09_released_slot_becomes_available(manager):
    first = manager.register_vehicle("LEA-4521", "Ali Khan", "Car", entry_time=START)
    manager.register_vehicle("KHI-2002", "Sara Ahmed", "Motorcycle", entry_time=START)
    manager.exit_vehicle(first["ticket"].ticket_id, exit_time=START + timedelta(hours=1))
    slots = manager.get_slots()
    assert slots[0].is_available
    assert slots[0].registration_number is None
    assert slots[1].is_occupied
    again = manager.register_vehicle("LEA-4521", "Ali Khan", "Car", entry_time=START + timedelta(hours=2))
    assert again["ticket"].slot_number == 1
    assert again["ticket"].ticket_id != first["ticket"].ticket_id


def test_10_history_saved_after_exit(manager):
    manager.register_vehicle("LEA-4521", "Ali Khan", "Car", entry_time=START)
    manager.exit_vehicle("LEA-4521", exit_time=START + timedelta(minutes=90))
    saved = manager.get_history()[0]
    assert saved["ticket_id"] == "CP-1001"
    assert saved["duration_text"] == "1h 30m"
    assert saved["billable_hours"] == 2
    assert saved["fee"] == 100
    assert saved["status"] == "completed"
    payment = manager.database.get_transaction("CP-1001")
    assert payment["fee"] == 100


def test_11_dashboard_stats_update(manager):
    empty = manager.get_dashboard()
    assert empty["total_slots"] == 20
    assert empty["available"] == 20
    assert empty["occupied"] == 0
    assert empty["total_revenue"] == 0

    manager.register_vehicle("LEA-4521", "Ali Khan", "Car", entry_time=START)
    manager.register_vehicle("KHI-2002", "Sara Ahmed", "Motorcycle", entry_time=START)
    manager.exit_vehicle("LEA-4521", exit_time=START + timedelta(minutes=30))

    updated = manager.get_dashboard()
    assert updated["occupied"] == 1
    assert updated["available"] == 19
    assert updated["parked_count"] == 1
    assert updated["occupancy_percent"] == 5.0
    assert updated["total_revenue"] == 50
    assert updated["completed_sessions"] == 1
    assert updated["activity"][0].registration_number == "KHI-2002"

    report = manager.get_report()
    assert report["total_revenue"] == 50
    assert report["daily_revenue"] == [{"day": "2026-11-14", "revenue": 50.0}]


def test_12_data_persists_after_new_database_manager(tmp_path):
    path = tmp_path / "campuspark.db"
    first = ParkingManager(path)
    saved = first.register_vehicle("LEA-4521", "Ali Khan", "Car", entry_time=START)
    first.update_hourly_rates({"Car": 80, "Motorcycle": 30, "Van": 70})
    first.close()

    reopened = DatabaseManager(path)
    row = reopened.active_by_reg("LEA-4521")
    assert row["ticket_id"] == saved["ticket"].ticket_id
    assert reopened.fetch_slots()[0]["status"] == "occupied"
    assert reopened.get_rates()["Car"] == 80
    reopened.close()

    restarted = ParkingManager(path)
    found = restarted.find_parked("cp-1001")
    assert found.registration_number == "LEA-4521"
    assert restarted.get_rates()["Car"] == 80
    restarted.close()
