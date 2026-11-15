# Electricity Billing — slides

Twelve short slides.

---

## Slide 1 — Title

**Electricity Billing**

OOP lab project. Customers, meter readings, and monthly bills.

---

## Slide 2 — The problem

- We need a record of each customer and meter.
- A month should only be billed once.
- The bill should show slabs, a fixed charge, tax, and a late fee.
- The rows should still be there after the program stops.

---

## Slide 3 — What the screen does

Six pages: Dashboard, Customers, Meter Readings, Bills, Tariff, Bill History.

Streamlit draws the pages. SQLite stores the file `data/billing.db`.

---

## Slide 4 — The classes

- `Customer`, with `DomesticCustomer` and `CommercialCustomer`
- `MeterReading`
- `Bill`
- `TariffCalculator`
- `DatabaseManager` for SQL
- `BillingManager`, which has the database and uses the calculator

---

## Slide 5 — Inheritance and polymorphism

Both child classes inherit the name, CNIC, and meter.

Each one overrides `energy_charge`.

The calculator calls that method. It does not ask which subclass it got.

---

## Slide 6 — One reading

1. Pick the customer and the month.
2. Check the current reading is not below the previous one.
3. Stop if that month already exists.
4. Work out the units and make bill `EB-1001`.
5. Save the reading and the bill together.

---

## Slide 7 — The money

Domestic starts at 10, 20, then 30 PKR per unit, in blocks of 100.

Commercial starts at 20, then 40 for the rest.

Then add the fixed charge and tax.

After the due date, add 10% if it is still unpaid.

250 domestic units, paid on time: PKR 5,060.

---

## Slide 8 — The tables

`customers`, `meter_readings`, `bills`, `tariffs`, `settings`.

The meter number is unique. The customer plus the month is unique.

The Tariff page changes the saved rates. The class code stays the same.

---

## Slide 9 — The screen

White page, black text, grey sidebar, teal buttons.

Screenshots are in the README. A fresh clone has no customers until you add them.

---

## Slide 10 — Tests

Command: `python3 -m pytest tests -v`

**13 passed in 0.88s.** None failed.

That covers add customer, duplicate meter, bad readings, both slab types, tax, late fee, mark paid, unpaid bills, the dashboard, a restarted database, and opening every page.

---

## Slide 11 — Who did what

- **Student 1** — models, tariff and billing logic, wiring the manager into `app.py`.
- **Student 2** — database, forms, tests, and the write-ups.

We can both follow one bill from the button to the `bills` table.

---

## Slide 12 — One limit

On a laptop the file survives a restart.

On Streamlit Community Cloud a redeploy can delete it. For the viva we use a laptop.

`app.py` is still the file the Cloud app runs.
