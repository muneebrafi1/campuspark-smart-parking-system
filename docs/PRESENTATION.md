# CampusPark — presentation

**Smart Parking. Simplified.**

Twelve slides. Read the title, then the bullets. Do not read the speaker note word for word.

---

## Slide 1 — Title

**CampusPark**
Smart Parking. Simplified.

OOP lab project
A parking desk for a university campus

Speaker note: Say your names, then one sentence: we built a working attendant screen, not a slide-only design.

---

## Slide 2 — The problem

- The gate needs to know which slots are free.
- The same car must not be entered twice while it is still inside.
- On the way out, the fee has to be explainable.
- If the program stops, the list of parked cars must still be there.

Speaker note: A Python list would forget everyone when the script ends. That is why there is a database.

---

## Slide 3 — Objectives

- Check vehicles in and out.
- 20 slots, assigned automatically.
- Fees in PKR, with a written rounding rule.
- History, a dashboard, and simple charts.
- Classes a beginner can open and explain.

Speaker note: Point at the running app if you have it, not at this slide, when you say "working".

---

## Slide 4 — What the attendant sees

Seven pages:

1. Dashboard
2. Vehicle Entry
3. Parking Slots (green free, red taken)
4. Vehicle Exit, with the bill
5. Pricing
6. Parking History
7. Reports & Analytics

Speaker note: The screenshots in the README are from a real local run. A fresh install starts empty, which is what you want for a live demo.

---

## Slide 5 — Tech stack

- Python 3.12
- Streamlit for the screen (`app.py`)
- SQLite for the file `data/campuspark.db`
- pytest, 28 tests, all passing on the recorded run

Speaker note: We did not add a second database server. SQLite is a file. That is easy to show in a viva and easy to reset.

---

## Slide 6 — The classes

- `Vehicle` → `Car`, `Motorcycle`, `Van` (inheritance and overriding)
- `ParkingSlot` — occupy and release
- `ParkingTicket` — one visit
- `PaymentCalculator` — the bill
- `DatabaseManager` — all SQL
- `ParkingManager` — has the database and the calculator (composition)

Speaker note: Draw "manager has database" on the board if the class diagram feels crowded. Say "has", not "is".

---

## Slide 7 — One entry, step by step

1. The form calls `ParkingManager.register_vehicle`.
2. The text is cleaned. `lea-4521` becomes `LEA-4521`.
3. `Vehicle.create` builds a Car, Motorcycle, or Van.
4. The database takes the lowest free slot inside one transaction.
5. The page shows ticket `CP-1001` and the slot number.

If the car is already inside, or all 20 slots are red, nothing is saved.

Speaker note: Polymorphism is step 3. The manager does not contain three copies of the entry code.

---

## Slide 8 — The fee

- Minimum charge: **1 hour**
- Partial hour: **round up**
- Exact hours stay exact
- Default rates: Car 50, Motorcycle 30, Van 70 PKR per hour
- The Pricing page can change the rate. The next exit uses the new rate.

Example: a car for 1 hour 20 minutes is `2 × 50 = PKR 100`.

Speaker note: Offer to change the entry time to two hours ago and exit live. The breakdown shows duration, billable hours, rate, and total.

---

## Slide 9 — The database

Five tables: `vehicles`, `parking_slots`, `parking_tickets`, `transactions`, `pricing`.

- A ticket is the visit.
- A transaction is the money, written only on exit.
- A unique index blocks two active rows for the same registration.
- Queries use `?` placeholders.

Speaker note: If asked "why two tables?", say a parked car has a ticket but does not have a payment yet.

---

## Slide 10 — Tests that actually ran

Command: `python3 -m pytest tests -v`

**28 passed in 0.91s.** Zero failures.

The 12 brief cases are in `tests/test_spec_cases.py`: register, auto slot, second vehicle, occupied board, duplicate, full lot, exit, fee rounding, released slot, history, dashboard totals, and a new `DatabaseManager` on the same file.

Streamlit's own test runner also opened every page and parked a car through the form.

Speaker note: Do not say "it should pass". Say the command and the result. The full output is in the project report.

---

## Slide 11 — Who did what

Both of us can explain the whole app.

- **Student 1** — vehicle and parking models, allocation, fee calculation, wiring the manager into the app.
- **Student 2** — database class, dashboard and forms, tests, and the written docs.

The slot is chosen in `DatabaseManager.create_entry` so the SQL stays in one class. The button calls `ParkingManager`.

Speaker note: Be ready to trace one exit across both files. That is the question that checks you both understand it.

---

## Slide 12 — Limits and what we would add

- On your laptop the SQLite file survives restarts. We tested that.
- On Streamlit Community Cloud the disk can be wiped on redeploy. Fine for a short demo, not for a real semester of records.
- We would add a hosted database only if we had to keep cloud data. We left it out so the project stays readable.
- Later ideas: a QR ticket, more than one lot.

**CampusPark — Smart Parking. Simplified.**

Speaker note: End on the fee rule or the slot board, whichever the teacher reacted to. Do not open a new feature that is not in the code.
