# CampusPark slides

About 12 slides. Say the point, then show the screen if it is running.

---

## Slide 1 — Title

**CampusPark**
Smart Parking. Simplified.

OOP lab project. A parking desk for 20 campus slots.

---

## Slide 2 — The problem

- Which slots are free?
- The same car should not be entered twice while it is still inside.
- On the way out we need a fee we can explain.
- The list should still be there after the program stops.

---

## Slide 3 — What we built

Seven pages: Dashboard, Vehicle Entry, Parking Slots, Vehicle Exit, Pricing, Parking History, Reports.

Streamlit for the screen. SQLite for the file. Plain Python classes for the rules.

---

## Slide 4 — The classes

- `Vehicle`, and `Car` / `Motorcycle` / `Van` which override the rate and the type
- `ParkingSlot` — occupy and release
- `ParkingTicket` — one visit
- `PaymentCalculator` — the bill
- `DatabaseManager` — the SQL
- `ParkingManager` — has the database and the calculator

---

## Slide 5 — One entry

1. Clean the registration.
2. Make a Car, Motorcycle, or Van.
3. Stop if that plate is already parked.
4. Take the lowest free slot.
5. Save the ticket, for example `CP-1001`.

If all 20 slots are red, nothing is saved.

---

## Slide 6 — The fee

- Minimum 1 hour.
- A partial hour rounds up.
- Exact hours stay exact.
- Defaults: Car 50, Motorcycle 30, Van 70 PKR per hour.
- Pricing can change the rate. The next exit uses the new one.

A car for 1 hour 20 minutes is `2 x 50 = PKR 100`.

---

## Slide 7 — The database

Five tables: vehicles, parking slots, parking tickets, transactions, pricing.

A ticket is the visit. A transaction is the money, written only on exit.

Queries use `?` so the registration is data, not part of the SQL text.

---

## Slide 8 — The screen

White background, black text, one teal accent on the buttons.

The slot board uses green for free and red for taken. That is the only extra colour, so the board is easy to read.

Screenshots are in the README. A new clone starts with an empty lot.

---

## Slide 9 — Tests

Command: `python3 -m pytest tests -v`

**14 passed in 0.82s.** None failed.

The 12 lab cases are `test_01` to `test_12` in `tests/test_parking.py`. Two more tests open the Streamlit pages and submit the entry form.

---

## Slide 10 — Who did what

- **Student 1** — models, slot allocation, fees, connecting the manager to the app.
- **Student 2** — database, pages, entry and exit forms, tests, docs.

The slot query lives in `DatabaseManager`. The button calls `ParkingManager`. We can both walk through an exit.

---

## Slide 11 — A limit

On a laptop the SQLite file survives a restart. Test 12 checks that.

On Streamlit Community Cloud a redeploy can delete the file. Fine for a short demo. For the viva we run it locally.

---

## Slide 12 — End

CampusPark. Smart Parking. Simplified.

We can show an entry, the slot turning red, and the bill on exit.
