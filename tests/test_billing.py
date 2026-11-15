"""Lab checks for customers, readings, slabs, and saved bills."""

from datetime import date

import pytest

from database.database_manager import DatabaseManager
from services.billing_manager import BillingManager
from utils.exceptions import BillingError


def add_ali(manager, meter="M-1001", connection="domestic"):
    return manager.add_customer(
        "Ali Khan", "35202-1234567-1", "Street 4 Lahore", "03001234567", meter, connection
    )


def test_add_customer(manager):
    saved = add_ali(manager)
    assert saved["name"] == "Ali Khan"
    assert saved["meter_number"] == "M-1001"
    assert saved["connection_type"] == "Domestic"
    assert manager.search_customers("ali")[0]["id"] == saved["id"]


def test_duplicate_meter_rejected(manager):
    add_ali(manager)
    with pytest.raises(BillingError, match="already registered"):
        manager.add_customer(
            "Sara Ahmed", "42101-9999999-1", "Mall Road Lahore", "03007654321", "m-1001", "Commercial"
        )
    assert len(manager.search_customers("")) == 1


def test_reading_current_below_previous(manager):
    customer = add_ali(manager)
    with pytest.raises(BillingError, match="less than"):
        manager.add_reading(customer["id"], "2026-11", 500, 400, on_date=date(2026, 11, 10))
    assert manager.bills() == []


def test_duplicate_month_rejected(manager):
    customer = add_ali(manager)
    manager.add_reading(customer["id"], "2026-11", 100, 150, on_date=date(2026, 11, 10))
    with pytest.raises(BillingError, match="already has a reading"):
        manager.add_reading(customer["id"], "2026-11", 150, 180, on_date=date(2026, 11, 10))
    assert len(manager.bills()) == 1


def test_domestic_slab(manager):
    customer = add_ali(manager)
    # 250 units: 100x10 + 100x20 + 50x30 = 4500
    bill = manager.add_reading(customer["id"], "2026-11", 1000, 1250, on_date=date(2026, 11, 10))
    assert bill["units"] == 250
    assert bill["energy_charge"] == 4500
    assert bill["connection_type"] == "Domestic"


def test_commercial_slab(manager):
    customer = add_ali(manager, meter="M-2001", connection="commercial")
    # 250 units: 100x20 + 150x40 = 8000
    bill = manager.add_reading(customer["id"], "2026-11", 0, 250, on_date=date(2026, 11, 10))
    assert bill["energy_charge"] == 8000
    assert bill["connection_type"] == "Commercial"


def test_tax_and_fixed_charge(manager):
    customer = add_ali(manager)
    # 50 units: energy 500, fixed 100, tax 10% of 600 = 60, total 660
    bill = manager.add_reading(customer["id"], "2026-11", 0, 50, on_date=date(2026, 11, 10))
    assert bill["energy_charge"] == 500
    assert bill["fixed_charge"] == 100
    assert bill["tax_amount"] == 60
    assert bill["surcharge"] == 0
    assert bill["total"] == 660


def test_late_surcharge(manager):
    customer = add_ali(manager)
    bill = manager.add_reading(customer["id"], "2026-01", 0, 250, on_date=date(2026, 1, 10))
    assert bill["surcharge"] == 0
    assert bill["due_date"] == "2026-02-15"
    paid = manager.mark_paid(bill["bill_no"], date(2026, 2, 20))
    # 10% of 5060 = 506
    assert paid["surcharge"] == 506
    assert paid["total"] == 5566
    assert paid["status"] == "paid"


def test_mark_paid(manager):
    customer = add_ali(manager)
    bill = manager.add_reading(customer["id"], "2026-11", 0, 100, on_date=date(2026, 11, 10))
    paid = manager.mark_paid(bill["bill_no"], date(2026, 11, 12))
    assert paid["status"] == "paid"
    assert paid["surcharge"] == 0
    assert paid["paid_date"] == "2026-11-12"
    with pytest.raises(BillingError, match="already paid"):
        manager.mark_paid(bill["bill_no"], date(2026, 11, 13))


def test_unpaid_list(manager):
    customer = add_ali(manager)
    fresh = manager.add_reading(customer["id"], "2026-11", 0, 40, on_date=date(2026, 11, 10))
    old = manager.add_reading(customer["id"], "2026-01", 0, 100, on_date=date(2026, 1, 10))
    unpaid = manager.bills(status="Unpaid", on_date=date(2026, 11, 15))
    overdue = manager.bills(status="Overdue", on_date=date(2026, 11, 15))
    assert {row["bill_no"] for row in unpaid} == {fresh["bill_no"], old["bill_no"]}
    assert [row["bill_no"] for row in overdue] == [old["bill_no"]]
    assert overdue[0]["surcharge"] == 121


def test_dashboard_stats(manager):
    today = date(2026, 11, 15)
    customer = add_ali(manager)
    manager.add_reading(customer["id"], "2026-11", 0, 100, on_date=today)
    data = manager.dashboard(on_date=today)
    assert data["customers"] == 1
    assert data["bills_this_month"] == 1
    assert data["collected"] == 0
    assert data["pending"] == 1210
    assert data["total_billed"] == 1210
    manager.mark_paid(manager.bills()[0]["bill_no"], today)
    after = manager.dashboard(on_date=today)
    assert after["collected"] == 1210
    assert after["pending"] == 0


def test_persists_after_new_database_manager(tmp_path):
    path = tmp_path / "billing.db"
    first = BillingManager(path)
    first.add_customer(
        "Ali Khan", "35202-1234567-1", "Street 4 Lahore", "03001234567", "M-1001", "domestic"
    )
    first.close()

    reopened = DatabaseManager(path)
    row = reopened.find_by_meter("M-1001")
    assert row is not None
    assert row["name"] == "Ali Khan"
    assert row["connection_type"] == "Domestic"
    reopened.close()

    second = BillingManager(path)
    assert second.search_customers("M-1001")[0]["cnic"] == "35202-1234567-1"
    second.close()
