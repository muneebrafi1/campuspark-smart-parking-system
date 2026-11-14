# CampusPark viva guide

Read this once before the viva, with the code open. The goal is to explain the program in your own words. You do not need to memorize every line.

Both students should be able to answer every question below. The file split is only about who wrote the first version.

## What the app does

CampusPark is the screen a campus attendant uses at the gate.

- A vehicle arrives. The attendant types the registration, the owner, and the type (Car, Motorcycle, or Van).
- The program gives it the first free slot and a ticket id such as `CP-1001`.
- The slot turns red on the board.
- When the vehicle leaves, the attendant searches the registration or the ticket, sees the bill, and confirms. The slot turns green.
- The visit stays in the database. The dashboard, history, and reports read that same data.

The tagline on the screen is **Smart Parking. Simplified.**

## How the system is split

Think of three layers. This is the sentence to start with if you go blank.

1. **Screen** — `app.py`. Buttons, forms, colours. It does not contain the fee rule or SQL.
2. **Rules** — `ParkingManager` and `PaymentCalculator` in `services/`. They decide what is allowed and what the bill is.
3. **Storage** — `DatabaseManager` in `database/database_manager.py`. It is the only file that talks to SQLite.

The things being stored are objects from `models/`: a vehicle, a slot, and a ticket.

## What each class does

### `Vehicle`, `Car`, `Motorcycle`, `Van` (`models/vehicle.py`)

`Vehicle` is the parent. It remembers a registration number and an owner name. It does not know the price by itself. The three methods `get_vehicle_type`, `get_hourly_rate`, and `get_description` raise `NotImplementedError` in the parent, so you cannot forget to override them.

`Car` says it is a car, its default rate is PKR 50 per hour, and it describes itself as a standard campus vehicle. `Motorcycle` is PKR 30. `Van` is PKR 70.

`Vehicle.create("motorcycle", reg, owner)` looks at the word and returns a `Motorcycle` object. The caller can treat that object as a `Vehicle`.

Those default rates are the starting prices. If an admin changes Pricing, the database value is what the bill uses. The class default is the fallback and the number we seed the first time.

### `ParkingSlot` (`models/parking_slot.py`)

One numbered space. It is either `available` or `occupied`. `occupy` stores the registration, type, and ticket, and it refuses if the slot is already taken. `release` clears those fields. The database stores the same facts; this class is where the rule lives so it is not copied into random `if` statements.

### `ParkingTicket` (`models/parking_ticket.py`)

One visit. While the vehicle is inside, `status` is `parked` and `is_active` is true. `close` writes the exit time and the fee onto the object and sets the status to `completed`. Calling `close` twice raises an error.

### `PaymentCalculator` (`services/payment_calculator.py`)

Pure fee maths. It does not open the database. You give it the rates, a vehicle, and two times. It returns a dictionary with the duration, billable hours, rate, and total.

### `DatabaseManager` (`database/database_manager.py`)

Opens `data/campuspark.db`, creates tables, and runs every `SELECT`, `INSERT`, and `UPDATE`. Other files never import `sqlite3`.

### `ParkingManager` (`services/parking_manager.py`)

The object `app.py` keeps. It **has** a database manager and a fee calculator. That is composition. The entry page calls `register_vehicle`. The exit page calls `find_parked`, `preview_fee`, and `exit_vehicle`.

## How the objects talk to each other

**Entry**

```text
form  ->  ParkingManager.register_vehicle
            ->  helpers clean the text
            ->  Vehicle.create(...)          # a Car, Motorcycle, or Van
            ->  DatabaseManager.create_entry
                    ->  reject if this registration is already parked
                    ->  lowest free slot
                    ->  ParkingSlot.occupy
                    ->  INSERT vehicle, INSERT ticket, UPDATE slot
            ->  ParkingTicket is returned to the page
```

**Exit**

```text
search  ->  ParkingManager.find_parked
preview ->  Vehicle.create + PaymentCalculator.calculate
confirm ->  DatabaseManager.complete_exit
                ->  ParkingSlot.release
                ->  ticket status = completed
                ->  INSERT into transactions
```

The page then draws the breakdown. It does not multiply hours by rate itself.

## Inheritance, in one example

```python
vehicle = Vehicle.create("Van", "ISB-1104", "Campus Shuttle")
vehicle.get_vehicle_type()   # "Van"   — Van's method
vehicle.get_hourly_rate()    # 70      — Van's method
vehicle.get_description()    # Van's sentence
```

`vehicle` is also a `Vehicle`, because `Van` inherits from it. `registration_number` works even though `Van` does not write that property. It inherits the property from the parent.

If someone passes `"Bus"`, `create` raises `ValidationError`. There is no `Bus` class.

## Encapsulation, in one example

Inside `Car.__init__`, the parent stores `self._registration_number`. The underscore is the team's way of saying "use the property". The property is:

```python
@property
def registration_number(self):
    return self._registration_number
```

There is no `@registration_number.setter`. This line fails, and a test checks that:

```python
car.registration_number = "OTHER-1"   # AttributeError
```

Python will still let you write `car._registration_number = "OTHER-1"` if you insist. The underscore is a convention, not a lock. That is the honest answer if the teacher asks about private variables. We did not use double-underscore name mangling, because it is harder to read and does not add anything this program needs.

## Fee calculation

Times are stored as text like `2026-11-14 09:00:00` so SQLite can sort them.

`billable_hours` counts whole seconds between exit and entry.

- 0 seconds, or any stay up to 60 minutes: **1 hour**.
- 60 minutes exactly: **1 hour**.
- 60 minutes and 1 second: **2 hours**.
- 2 hours exactly: **2 hours**.

The total is `billable hours × hourly rate`, rounded to 2 decimal places. With the default whole-rupee rates the total is a whole number.

If the exit time is earlier than the entry time, the calculator raises `ValidationError` and nothing is saved.

The rate comes from the `pricing` table when that vehicle type is listed. `rate_for` only calls `vehicle.get_hourly_rate()` when the saved table has no row for that type. That second path is there so the subclass method is really used, and a test covers it.

## What is stored

Five tables. You should be able to say what each one is for without reading the SQL.

- `vehicles` — who came in (registration, owner, type, time). A repeat visit adds another row. We do not try to keep a single master row per car.
- `parking_slots` — 20 rows, slot numbers 1 to 20. Occupied rows remember the registration, type, and ticket.
- `parking_tickets` — one row per visit, for the whole life of that visit. Status changes from `parked` to `completed`. The ticket row does not hold the money.
- `transactions` — one row per completed visit. This is the bill: exit time, duration text, billable hours, rate, fee.
- `pricing` — three rows, one rate per type.

History is a `LEFT JOIN` of tickets and transactions. A parked visit has no payment yet, so exit, duration, and fee show as a dash.

The unique index `idx_one_active_registration` is only on rows where `status = 'parked'`. That is why the same registration can appear again after exit.

## Validation the attendant will see

- Registration is required, 3 to 15 characters, letters, numbers, spaces, or hyphens. `lea-4521` is stored as `LEA-4521`, so a second spelling cannot sneak in.
- Owner name is required, 3 to 60 characters, letters and a few marks (`'`, `.`, `-`). Digits are rejected.
- Type must be Car, Motorcycle, or Van.
- A registration that is already inside is rejected. The message names the slot and the ticket.
- Slot 21 does not exist. When all 20 are occupied, entry raises `ParkingFullError`.
- You cannot exit a vehicle that is not parked.
- A rate must be greater than 0 and at most 100000.

Empty fields never occupy a slot. The tests check that the active list stays empty.

## Errors

`utils/exceptions.py` has one parent, `ParkingError`, and a few children: `ValidationError`, `DuplicateVehicleError`, `ParkingFullError`, `VehicleNotFoundError`, `DatabaseError`. The pages catch `ParkingError` and call `st.error`. A database failure is wrapped so the attendant does not see the raw SQLite message.

## How to run it in the viva

```bash
pip install -r requirements.txt
streamlit run app.py
python3 -m pytest tests -v
```

Run the commands from the project folder. If the teacher asks "where is the data?", open `data/campuspark.db` only after the app has been started once. It is not in git.

## 24 viva questions

### 1. What problem does CampusPark solve?

A campus lot needs a record of who is inside, which slot they use, and what they should pay on the way out. Paper or a single list gets out of date. CampusPark keeps those records in SQLite and shows them on one screen.

### 2. Why is this an OOP project and not one long script?

The lot has clear "things": vehicles, slots, tickets, a fee rule, and a database. Each thing is a class with its own data and methods. The screen asks the manager to do the work. That is easier to test and easier to explain than a script full of loose variables.

### 3. What is the difference between a class and an object here?

`Car` is the class, the design. `Car("LEA-4521", "Ali Khan")` is an object, one car with those details. Another call with a different registration is a different object of the same class.

### 4. Why do Car, Motorcycle, and Van inherit from Vehicle?

They all have a registration and an owner. That data and those properties are written once in `Vehicle`. Each child only overrides what is different: the type name, the default hourly rate, and the description.

### 5. Show overriding.

Open `models/vehicle.py`. `Car.get_hourly_rate` returns 50. `Motorcycle.get_hourly_rate` returns 30. `Van.get_hourly_rate` returns 70. Same method name, different body. The parent version raises `NotImplementedError` so a half-finished subclass is obvious.

### 6. Show polymorphism.

`Vehicle.create` returns different subclasses. This loop does not mention `Car` or `Van` by name, but each object answers for itself:

```python
for vehicle in vehicles:
    print(vehicle.get_vehicle_type(), vehicle.get_hourly_rate())
```

`PaymentCalculator.rate_for` is the same idea. It calls `vehicle.get_vehicle_type()` and, if needed, `vehicle.get_hourly_rate()`.

### 7. What is encapsulation in your code?

The registration is stored in `_registration_number` and read through the `registration_number` property. Callers do not get a setter. A test in `tests/test_payment_and_models.py` proves assignment raises `AttributeError`. The fee calculator also copies the rates dict into `_rates` and its `rates` property returns a copy, so a caller cannot change the calculator's numbers by editing the dictionary it received.

### 8. What is composition? Why not inheritance for the manager?

`ParkingManager.__init__` creates a `DatabaseManager` and a `PaymentCalculator` and keeps them in `self._database` and `self._calculator`. The manager is not a database and not a calculator. It uses them. Inheritance would say "a manager is a database", which is the wrong sentence. "A manager has a database" is the right one.

### 9. Who chooses the slot number?

`DatabaseManager.create_entry` runs:

```sql
SELECT ... FROM parking_slots
WHERE status = 'available'
ORDER BY slot_number
LIMIT 1
```

So the lowest free number wins. If slot 1 is freed and slot 2 is still taken, the next car gets slot 1 again. `ParkingSlot.occupy` is called before the `UPDATE`, so a slot that is already occupied cannot be assigned. The page never asks the attendant to type a slot number.

### 10. What happens if the lot is full?

The query above returns no row. The method raises `ParkingFullError` with a message that includes the total number of slots (20 in the real app). The transaction rolls back, so no ticket is left half-saved. `test_06_parking_full_rejected` parks 20 vehicles and checks that the 21st is rejected.

### 11. How do you stop the same car being entered twice?

Two ways, on purpose. The Python code looks for a `parked` ticket with that registration and raises `DuplicateVehicleError`. The database also has a unique index on `registration_number` where `status = 'parked'`. If two saves raced, SQLite would still reject the second insert. After exit, the status is `completed`, so the index allows a new parked row. `test_09` checks that the same registration can enter again and that it receives the lowest free slot.

### 12. Why is the registration uppercased?

`normalize_registration` trims spaces and uppercases the text. `lea-4521` and `LEA-4521` become one value. Otherwise the same car could be "two" vehicles. The owner name is also trimmed, but it keeps its capital letters.

### 13. Explain the bill for a car that stays 1 hour 20 minutes.

Duration text is `1h 20m`. That is more than 1 hour and not an exact hour, so billable hours is 2. Default car rate is PKR 50. Total is PKR 100. `test_08_fee_minimum_one_hour_and_round_up` asserts this through `exit_vehicle`, not only through the calculator.

### 14. A motorcycle leaves after 10 minutes. What is the fee?

Minimum 1 hour at PKR 30, so PKR 30. An exact 1 hour motorcycle stay is also PKR 30. A stay of 1 hour and 1 minute is 2 hours, PKR 60.

### 15. A van stays exactly 3 hours. What is the fee?

Exactly 3 billable hours, not 4. `3 × 70 = PKR 210`. The test checks this.

### 16. What if the admin changes the car rate to 80 while a car is still inside?

The next exit uses 80. The class method `Car.get_hourly_rate` still returns 50, because that is the default written in the class. `PaymentCalculator` prefers the saved rate. `test_rate_change_is_used_on_the_next_exit` parks a car, changes the rate, exits, and expects `2 × 40` in that particular test (the test sets the rate to 40). The idea is the same for 80.

### 17. Why are there both `parking_tickets` and `transactions`?

A ticket is the visit: who, where, when they arrived, and whether they are still inside. A transaction is the money: when they left, how many hours were billed, and the fee. History joins them. Parked visits have a ticket and no transaction yet. Putting the fee only on the ticket would mix "still inside" with "already paid".

### 18. How do you know the data survives a restart?

`test_12_data_persists_after_new_database_manager` parks a car, closes the first manager, constructs a **new** `DatabaseManager` on the same file, and reads the parked row and the occupied slot back. It also checks that a changed car rate is still 80. A second `ParkingManager` can find the ticket. That is the same thing that happens when you stop Streamlit and start it again on your laptop.

### 19. Why does the Streamlit app not open a new database on every click?

`load_manager` in `app.py` is wrapped with `@st.cache_resource`. One `ParkingManager` stays alive for the Streamlit process. Each action still reads and writes the SQLite file, so a browser refresh shows the saved rows. The cache is only the Python object, not a second copy of the data.

### 20. What is a parameterized query? Show one.

A value from the form is never pasted into the SQL string. This is the duplicate check:

```python
self._connection.execute(
    """
    SELECT ticket_id, slot_number
    FROM parking_tickets
    WHERE registration_number = ? AND status = 'parked'
    """,
    (registration_number,),
)
```

The `?` is the placeholder. The registration goes in the tuple. If someone typed SQL into the registration box, it would be stored as text or rejected by validation. It would not become part of the statement.

### 21. What do you do when SQLite throws?

`create_entry` and `complete_exit` catch `sqlite3.Error` and raise `DatabaseError` with a short sentence. `sqlite3.IntegrityError` on entry becomes `DuplicateVehicleError`. The `with self._connection` block rolls the transaction back if we raise, so a failed exit does not free the slot and also keep the ticket open, or the other way around.

### 22. What does the dashboard count as revenue?

`SUM(fee)` from `transactions` only. A car that is still parked has not paid, so it is not in the revenue total. It is counted in "vehicles parked" and "occupied". `test_11` checks the numbers after one exit: 1 slot still occupied, 19 free, revenue equal to that one bill, and one completed session.

### 23. What will not work well on Streamlit Community Cloud?

Page changes and refreshes are fine. The SQLite file is on the server's disk, and that disk is ephemeral. A new deploy or a reboot can delete `data/campuspark.db`. Say that clearly. For marking, run the app on a computer. We did not add a second hosted database, so the project stays on the standard library.

### 24. What did each student do, and can you explain the other half?

Student 1 wrote the vehicle and parking models, the fee calculator, and the manager methods that tie entry, allocation, and exit together, and connected them from `app.py`. Student 2 wrote `DatabaseManager`, the Streamlit pages (dashboard, forms, slot board), the tests, and these documents. The slot `SELECT` lives in the database class because all SQL lives there. The manager is what the button calls. You should be able to trace one entry and one exit across both files without notes.

## If you forget a method name

Say what the object is responsible for, then find the method. The names are ordinary verbs: `register_vehicle`, `exit_vehicle`, `occupy`, `release`, `calculate`, `create_entry`, `complete_exit`. There is no extra framework to remember.
