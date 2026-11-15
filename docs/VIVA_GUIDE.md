# Viva guide

Read this with the code open. Answer in your own words.

## What the program does

We store electricity customers and their meter readings. When a reading is saved, a bill is made for that month. The bill uses slab rates, a fixed charge, and tax. If it is still unpaid after the due date, a late percent is added. The attendant can mark a bill paid and look up old bills.

## The classes

`Customer` keeps `_name`, `_cnic`, `_address`, `_phone`, and `_meter_number`. Other code reads them through properties. `get_connection_type` and `energy_charge` in the parent raise `NotImplementedError`, so a child class has to write them. That is abstraction in a simple form.

`DomesticCustomer` and `CommercialCustomer` inherit from `Customer`. Each one overrides `energy_charge`. Domestic uses three slabs. Commercial uses two. `TariffCalculator.quote` calls `customer.energy_charge(units, rates)` and does not check the class. That is polymorphism.

`MeterReading` refuses a current reading that is lower than the previous one.

`Bill.mark_paid` refuses to pay a bill that is already paid.

`BillingManager` is not a database. It has one (`self._db`) and it builds a `TariffCalculator` when it needs prices. That is composition.

`DatabaseManager` is the only file that imports `sqlite3`.

## How a bill is made

1. The form calls `BillingManager.add_reading`.
2. The month is checked (`2026-11`). If that meter already has that month, we stop.
3. `MeterReading` checks the numbers and works out the units.
4. `Customer.create` makes a domestic or commercial object from the saved type.
5. `TariffCalculator.quote` asks that object for the energy charge, then adds the fixed charge and tax.
6. The reading and the bill are saved in one transaction. The bill number looks like `EB-1001`.

The due date is a number of days into the next month. The default is 15, so a November bill is due on 15 December. If you mark it paid after that date, the late percent is added to the total.

## Tables

- `customers` — who has a meter.
- `meter_readings` — previous, current, and units for one month.
- `bills` — the money for that reading.
- `tariffs` — slab sizes, rates, fixed charge, and tax for each connection type.
- `settings` — late percent and due days.

## Questions

**1. Why not one long script?**
A customer, a reading, and a bill are different things. Each one is a class. The page only calls the manager.

**2. What is inheritance here?**
`DomesticCustomer(Customer)` and `CommercialCustomer(Customer)`. They get the name and meter from the parent. They replace `energy_charge`.

**3. What is polymorphism here?**
`quote` calls `customer.energy_charge(...)`. If the object is domestic, the three-slab method runs. If it is commercial, the two-slab method runs. The calculator does not have an `if` for that.

**4. What is encapsulation here?**
The name is stored in `_name` and read with the `name` property. There is no setter. The underscore is a convention. Python does not really hide it.

**5. What is abstraction here?**
The parent `energy_charge` is not a real price. It raises `NotImplementedError`. Only a real connection type can be billed.

**6. Why does the manager not inherit from the database?**
A manager is not a database. It uses one. See `self._db = DatabaseManager(...)` in `BillingManager`.

**7. What happens if the meter number is already used?**
`meter_number` is UNIQUE. The insert fails and we raise `BillingError` saying the meter is already registered. `m-1001` and `M-1001` are the same meter because we store it in uppercase.

**8. What happens if the current reading is lower?**
`MeterReading.__init__` raises `BillingError`. No row is saved.

**9. Can I enter November twice?**
No. There is a unique pair of customer and month. The manager also checks before saving and says the month already has a reading.

**10. Walk through 250 domestic units.**
100 x 10 = 1000, next 100 x 20 = 2000, last 50 x 30 = 1500. Energy is PKR 4,500. Fixed charge is 100. Tax is 10% of 4,600, which is 460. Total is PKR 5,060 if it is paid on time.

**11. How is commercial different?**
The first 100 units use the commercial slab 1 rate (20). The rest use slab 2 rate (40). Slab 3 is not used. 250 units are 100 x 20 + 150 x 40 = 8,000, then fixed 200 and 10% tax.

**12. When is the late fee added?**
Only if the date is after `due_date`. Paying on the due date does not add it. Paying the next day adds `late_percent` of the energy + fixed + tax. The default is 10%.

**13. What is saved when a bill is marked paid?**
`status` becomes `paid`, `paid_date` is stored, and `total` includes the surcharge if it was late. A second click says the bill is already paid.

**14. What does the dashboard count?**
Customers in the table. Bills whose month is this month. Collected is the sum of paid totals. Pending is what unpaid bills owe today, including a late fee if they are overdue. Total billed is collected plus pending.

**15. How do you know the data survives a restart?**
`test_persists_after_new_database_manager` closes the manager, opens a new `DatabaseManager` on the same file, and reads the customer back.

**16. Why `?` in the SQL?**
The meter number is data, not part of the sentence. Example: `WHERE meter_number = ?` with the value in a tuple.

**17. What if SQLite throws?**
We catch `sqlite3.Error` and raise `BillingError` with a short message. Saving a reading and its bill uses `with self._conn`, so a failure rolls both back.

**18. What is weak on Streamlit Cloud?**
The database file can disappear when the server redeploys. Use a laptop for the demo if you need the rows to stay.

**19. Who wrote what?**
Student 1: models, tariff calculator, billing manager, and the calls from `app.py`. Student 2: `DatabaseManager`, the pages, tests, and docs. Both of us should trace one bill from the form to the `bills` table.
