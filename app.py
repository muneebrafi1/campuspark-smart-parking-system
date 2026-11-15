"""Electricity billing. Run with: streamlit run app.py"""

import os
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.billing_manager import BillingManager
from utils.exceptions import BillingError

PAGES = ["Dashboard", "Customers", "Meter Readings", "Bills", "Tariff", "Bill History"]
TYPES = ["Domestic", "Commercial"]


def db_path():
    return os.environ.get("BILLING_DB", str(ROOT / "data" / "billing.db"))


@st.cache_resource
def load_manager(path):
    return BillingManager(path)


def money(amount):
    value = float(amount)
    return f"PKR {value:,.0f}" if value.is_integer() else f"PKR {value:,.2f}"


def customer_table(rows):
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([{
        "ID": row["id"],
        "Name": row["name"],
        "CNIC": row["cnic"],
        "Phone": row["phone"],
        "Meter": row["meter_number"],
        "Type": row["connection_type"],
        "Address": row["address"],
    } for row in rows])


def bill_table(rows):
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([{
        "Bill": row["bill_no"],
        "Customer": row["name"],
        "Meter": row["meter_number"],
        "Month": row["month"],
        "Units": row["units"],
        "Due": row["due_date"],
        "Amount": money(row["amount_due"]),
        "Status": "Overdue" if row["overdue"] else row["status"].title(),
    } for row in rows])


def show_bill(bill):
    st.subheader(f"{bill['bill_no']} · {bill['name']}")
    a, b, c = st.columns(3)
    a.metric("Units", bill["units"])
    b.metric("Energy", money(bill["energy_charge"]))
    c.metric("Amount due", money(bill["amount_due"]))
    st.write(f"Meter {bill['meter_number']} · {bill['connection_type']} · month {bill['month']}")
    st.write(f"Fixed charge {money(bill['fixed_charge'])}")
    st.write(f"Tax {money(bill['tax_amount'])}")
    st.write(f"Late surcharge {money(bill['surcharge'])}")
    st.write(f"Due {bill['due_date']} · status {bill['status']}")
    if bill["overdue"]:
        st.caption("Past the due date, so the late surcharge is included.")


def page_dashboard(manager):
    st.header("Dashboard")
    data = manager.dashboard()
    top = st.columns(3)
    top[0].metric("Customers", data["customers"])
    top[1].metric("Bills this month", data["bills_this_month"])
    top[2].metric("Total billed", money(data["total_billed"]))
    bottom = st.columns(2)
    bottom[0].metric("Collected", money(data["collected"]))
    bottom[1].metric("Pending", money(data["pending"]))
    left, right = st.columns(2)
    with left:
        st.subheader("Billed by month")
        if data["by_month"]:
            st.bar_chart(pd.DataFrame(data["by_month"]), x="month", y="amount")
        else:
            st.info("No bills yet.")
    with right:
        st.subheader("Customers by type")
        st.bar_chart(pd.DataFrame(data["by_type"]), x="connection_type", y="customers")


def page_customers(manager):
    st.header("Customers")
    with st.form("add_customer", clear_on_submit=True):
        name = st.text_input("Name", key="cust_name")
        cnic = st.text_input("CNIC or ID", key="cust_cnic")
        phone = st.text_input("Phone", key="cust_phone")
        meter = st.text_input("Meter number", key="cust_meter")
        address = st.text_input("Address", key="cust_address")
        connection = st.selectbox("Connection", TYPES, key="cust_type")
        submitted = st.form_submit_button("Add customer", type="primary")
    if submitted:
        try:
            saved = manager.add_customer(name, cnic, address, phone, meter, connection)
            st.success(f"Saved {saved['name']} on meter {saved['meter_number']}.")
        except BillingError as exc:
            st.error(str(exc))

    search = st.text_input("Search", placeholder="Name, CNIC, or meter", key="cust_search")
    rows = manager.search_customers(search)
    if rows:
        st.dataframe(customer_table(rows), hide_index=True, width="stretch")
    else:
        st.info("No customers match.")
        return

    labels = [f"{row['id']} · {row['name']} · {row['meter_number']}" for row in rows]
    choice = st.selectbox("Update or delete", labels, key="cust_pick")
    chosen = rows[labels.index(choice)]
    with st.form("edit_customer"):
        name = st.text_input("Name", value=chosen["name"])
        cnic = st.text_input("CNIC or ID", value=chosen["cnic"])
        phone = st.text_input("Phone", value=chosen["phone"])
        meter = st.text_input("Meter number", value=chosen["meter_number"])
        address = st.text_input("Address", value=chosen["address"])
        connection = st.selectbox("Connection", TYPES, index=TYPES.index(chosen["connection_type"]))
        save = st.form_submit_button("Save changes")
    if save:
        try:
            manager.update_customer(chosen["id"], name, cnic, address, phone, meter, connection)
            st.success("Customer updated.")
        except BillingError as exc:
            st.error(str(exc))
    if st.button("Delete customer"):
        try:
            manager.delete_customer(chosen["id"])
            st.success("Customer deleted.")
        except BillingError as exc:
            st.error(str(exc))


def page_readings(manager):
    st.header("Meter Readings")
    customers = manager.search_customers("")
    if not customers:
        st.info("Add a customer first.")
        return
    labels = [f"{row['id']} · {row['name']} · {row['meter_number']}" for row in customers]
    with st.form("reading_form"):
        choice = st.selectbox("Customer", labels, key="read_customer")
        month = st.text_input("Month", value=date.today().strftime("%Y-%m"), key="read_month")
        previous = st.number_input("Previous reading", min_value=0.0, step=1.0, key="read_prev")
        current = st.number_input("Current reading", min_value=0.0, step=1.0, key="read_curr")
        submitted = st.form_submit_button("Save reading and bill", type="primary")
    if submitted:
        customer_id = int(choice.split(" · ")[0])
        try:
            bill = manager.add_reading(customer_id, month, previous, current)
            st.success(
                f"Bill {bill['bill_no']} for {bill['units']} units. Amount {money(bill['amount_due'])}."
            )
            show_bill(bill)
        except BillingError as exc:
            st.error(str(exc))


def page_bills(manager):
    st.header("Bills")
    status = st.selectbox("Show", ["All", "Unpaid", "Overdue", "Paid"], key="bill_status")
    rows = manager.bills(status=status)
    if not rows:
        st.info("No bills in this list.")
        return
    st.dataframe(bill_table(rows), hide_index=True, width="stretch")
    labels = [f"{row['bill_no']} · {row['name']} · {row['month']}" for row in rows]
    choice = st.selectbox("Open a bill", labels, key="bill_pick")
    bill = rows[labels.index(choice)]
    show_bill(bill)
    if bill["status"] == "unpaid":
        paid_on = st.date_input("Payment date", value=date.today(), key="pay_date")
        if st.button("Mark paid", type="primary", key="pay_button"):
            try:
                saved = manager.mark_paid(bill["bill_no"], paid_on)
                st.success(f"{saved['bill_no']} marked paid. Total {money(saved['total'])}.")
            except BillingError as exc:
                st.error(str(exc))


def page_tariff(manager):
    st.header("Tariff")
    st.write("Domestic uses three slabs. Commercial uses the first slab, then slab 2 rate for the rest.")
    current = manager.get_tariffs()
    fields = [
        ("slab1_units", "slab 1 units", 0.0, None),
        ("slab1_rate", "slab 1 rate", 0.0, None),
        ("slab2_units", "slab 2 units", 0.0, None),
        ("slab2_rate", "slab 2 rate", 0.0, None),
        ("slab3_rate", "slab 3 rate", 0.0, None),
        ("fixed_charge", "fixed charge", 0.0, None),
        ("tax_percent", "tax %", 0.0, 100.0),
    ]
    with st.form("tariff_form"):
        edited = {}
        columns = st.columns(2)
        for column, name in zip(columns, TYPES):
            rates = current["tariffs"][name]
            column.subheader(name)
            edited[name] = {}
            for key, label, low, high in fields:
                kwargs = {"min_value": low, "value": float(rates[key]), "key": f"{name}_{key}"}
                if high is not None:
                    kwargs["max_value"] = high
                edited[name][key] = column.number_input(f"{name} {label}", **kwargs)
        late = st.number_input("Late surcharge %", value=float(current["late_percent"]), min_value=0.0, max_value=100.0)
        due_days = st.number_input("Due days into next month", value=float(current["due_days"]), min_value=1.0, max_value=60.0, step=1.0)
        saved = st.form_submit_button("Save tariff")
    if saved:
        try:
            manager.update_tariffs(edited, late, due_days)
            st.success("Tariff saved. New bills use these rates.")
        except BillingError as exc:
            st.error(str(exc))


def page_history(manager):
    st.header("Bill History")
    left, right = st.columns(2)
    search = left.text_input("Customer, meter, or bill no", key="hist_search")
    month = right.text_input("Month", placeholder="2026-11", key="hist_month")
    rows = manager.bills(search=search, month=month)
    if rows:
        st.dataframe(bill_table(rows), hide_index=True, width="stretch")
    else:
        st.info("Nothing matches.")


def main():
    st.set_page_config(page_title="Electricity Billing", page_icon="E", layout="wide")
    try:
        manager = load_manager(db_path())
    except BillingError as exc:
        st.error(str(exc))
        st.stop()

    st.sidebar.title("Electricity Billing")
    st.sidebar.caption("Campus OOP lab")
    page = st.sidebar.radio("Menu", PAGES, label_visibility="collapsed")
    pages = {
        "Dashboard": page_dashboard,
        "Customers": page_customers,
        "Meter Readings": page_readings,
        "Bills": page_bills,
        "Tariff": page_tariff,
        "Bill History": page_history,
    }
    try:
        pages[page](manager)
    except BillingError as exc:
        st.error(str(exc))


if __name__ == "__main__":
    main()
