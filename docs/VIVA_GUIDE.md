# Viva guide

Read this with the code open. Say it in your own words.

## What the program does

An attendant types in a vehicle. The program gives it the lowest free slot and a ticket number. The slot shows as occupied. When the vehicle leaves, the program works out the fee, saves it, and frees the slot. The records are in a SQLite file, so a refresh does not delete them.

## The classes

`Vehicle` stores the registration and the owner in `_registration_number` and `_owner_name`. You read them with properties. `Car`, `Motorcycle`, and `Van` inherit from `Vehicle` and override `get_type` and `get_hourly_rate`.

`Vehicle.create("car", reg, owner)` returns a `Car` object. The rest of the code can call `get_hourly_rate()` without checking which child it is. That is polymorphism.

`ParkingSlot` is one space. `occupy` fills it. `release` clears it. If you occupy a slot that is already taken, it raises `ParkingError`.

`ParkingTicket` is one visit. `close` sets the exit time, the fee, and the status to completed.

`PaymentCalculator` does the maths only. It does not touch the database.

`DatabaseManager` is the only class that uses `sqlite3`.

`ParkingManager` has a database object and a calculator object. That is composition. The manager is not a database. It uses one.

## Entry, in order

1. The form calls `ParkingManager.register_vehicle`.
2. The registration is cleaned (`lea-4521` becomes `LEA-4521`) and the owner name is checked.
3. `Vehicle.create` makes a Car, Motorcycle, or Van.
4. If that registration is already parked, we stop.
5. `first_free_slot` gets the lowest available slot number.
6. `ParkingSlot.occupy` marks it, then `save_entry` writes the vehicle, the ticket, and the slot in one transaction.

If all 20 slots are taken, the message says the lot is full and nothing is saved.

## Exit, in order

1. Search by registration or by ticket id (`CP-1001`).
2. `preview_fee` builds the bill but does not save it.
3. `save_exit` marks the ticket completed, inserts a row in `transactions`, and sets the slot back to available.
4. `ticket.close` updates the ticket object in memory.

## The fee

Count the seconds from entry to exit.

- 0 to 60 minutes: 1 hour.
- Exactly 1 hour: 1 hour.
- 1 hour and 1 minute: 2 hours.
- Exactly 3 hours: 3 hours.

Fee = billed hours times the hourly rate. Default rates are Car 50, Motorcycle 30, Van 70. If the admin changes Pricing, the next exit uses the new rate. `Car.get_hourly_rate()` still returns 50. That method is the starting price. The saved rate wins when it exists.

## The tables

- `vehicles` — who arrived.
- `parking_slots` — slots 1 to 20.
- `parking_tickets` — every visit, parked or completed.
- `transactions` — the bill, only after exit.
- `pricing` — the three hourly rates.

There is a unique index so only one parked row can exist for a registration. After exit the status is completed, so the same car can enter again.

## Questions

**1. Why classes instead of one long script?**
The lot is made of things: a vehicle, a slot, a ticket, a fee, a database. Each one is a class. The page only asks the manager to do the work.

**2. What is the difference between the class `Car` and one car object?**
`Car` is the design. `Car("LEA-4521", "Ali Khan")` is one car. Another registration is another object.

**3. What did you override?**
`get_type` and `get_hourly_rate`. Car returns `"Car"` and 50. Motorcycle returns `"Motorcycle"` and 30. Van returns `"Van"` and 70. The parent versions are the defaults the children replace.

**4. Where is polymorphism?**
`Vehicle.create` returns different subclasses. `PaymentCalculator.rate_for` calls `vehicle.get_type()` and, if needed, `vehicle.get_hourly_rate()`. It does not have a separate function for each type.

**5. What is encapsulation here?**
The registration is stored in `_registration_number`. Other code uses the property `registration_number`. There is no setter. The underscore means "please use the property". Python will still let you touch `_registration_number` if you try. It is a convention, not a lock.

**6. Why does the manager not inherit from the database?**
A manager is not a database. It has a database. Look at `self._db = DatabaseManager(...)` and `self._fees = PaymentCalculator(...)` in `ParkingManager.__init__`.

**7. Who picks the slot?**
`DatabaseManager.first_free_slot` runs `SELECT ... WHERE status = 'available' ORDER BY slot_number LIMIT 1`. The lowest number wins. The page never asks the attendant to type a slot.

**8. What if the lot is full?**
`first_free_slot` returns nothing. `register_vehicle` raises `ParkingError` with the word "full". The test parks 20 vehicles and checks that the 21st fails.

**9. What if the same car is entered twice?**
We look for a parked ticket with that registration and raise `ParkingError`. SQLite also has a unique index on parked registrations, so a second insert would fail too. After exit, the same registration can park again and gets the lowest free slot.

**10. Why uppercase the registration?**
So `lea-4521` and `LEA-4521` are the same car.

**11. A car stays 1 hour 20 minutes. What is the bill?**
Duration is `1h 20m`. Billed hours is 2. At PKR 50 the fee is PKR 100. Test 08 checks this through `exit_vehicle`.

**12. A motorcycle stays 20 minutes. What is the bill?**
1 hour minimum, PKR 30.

**13. A van stays exactly 3 hours. What is the bill?**
3 hours, not 4. `3 x 70 = PKR 210`.

**14. The admin changes the car rate while a car is inside. Which rate is used?**
The rate at exit time. The class method still returns 50.

**15. Why both tickets and transactions?**
A parked car has a ticket but has not paid yet. The transaction row is the money. History joins the two tables.

**16. How do you know data survives a restart?**
Test 12 closes the manager, opens a new `DatabaseManager` on the same file, and reads the parked car and the changed rate back.

**17. Why is the manager cached in Streamlit?**
`@st.cache_resource` keeps one `ParkingManager` for the running app. The rows are still read from the file on each action, so a refresh shows what was saved.

**18. Show a parameterized query.**
In `active_by_reg` the registration is passed as `(registration_number,)` next to a `?`. It is not pasted into the SQL string.

**19. What happens if SQLite fails?**
`save_entry` and `save_exit` catch `sqlite3.Error` and raise `ParkingError` with a short sentence. The `with self._conn` block rolls the transaction back, so we do not save half an entry.

**20. What is weak about running this on Streamlit Cloud?**
The SQLite file is on the server disk. A redeploy or reboot can delete it. Clicks and refreshes are fine while that server is up. We run the demo on a laptop when we need the data to stay.

**21. What did each student write?**
Student 1: models, slot choice from the manager's point of view, fees, and calling the manager from `app.py`. Student 2: `DatabaseManager`, the pages, tests, and docs. Both of us can trace one entry and one exit across both files.
