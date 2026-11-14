"""CampusPark. Run with: streamlit run app.py"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.parking_manager import ParkingManager
from utils.exceptions import ParkingError

PAGES = [
    "Dashboard", "Vehicle Entry", "Parking Slots", "Vehicle Exit",
    "Pricing", "Parking History", "Reports",
]
TYPES = ["Car", "Motorcycle", "Van"]


def db_path():
    return os.environ.get("CAMPUSPARK_DB", str(ROOT / "data" / "campuspark.db"))


@st.cache_resource
def load_manager(path):
    return ParkingManager(path)


def show_time(value):
    return "—" if not value else value.strftime("%d %b %Y, %I:%M %p")


def money(amount):
    if amount is None:
        return "—"
    value = float(amount)
    return f"PKR {value:,.0f}" if value.is_integer() else f"PKR {value:,.2f}"


def history_table(records):
    rows = []
    for rec in records:
        parked = rec["status"] == "parked"
        rows.append({
            "Ticket": rec["ticket_id"],
            "Registration": rec["registration_number"],
            "Owner": rec["owner_name"],
            "Type": rec["vehicle_type"],
            "Slot": rec["slot_number"],
            "Entry": show_time(rec["entry_time"]),
            "Exit": "—" if parked else show_time(rec["exit_time"]),
            "Duration": "—" if parked else (rec["duration_text"] or "—"),
            "Billed hours": "—" if parked else rec["billable_hours"],
            "Fee": "—" if parked else money(rec["fee"]),
            "Status": "Parked" if parked else "Completed",
        })
    return pd.DataFrame(rows)


def page_dashboard(manager):
    st.header("Dashboard")
    data = manager.get_dashboard()
    top = st.columns(3)
    top[0].metric("Total slots", data["total_slots"])
    top[1].metric("Available", data["available"])
    top[2].metric("Occupied", data["occupied"])
    bottom = st.columns(3)
    bottom[0].metric("Occupancy", f"{data['occupancy_percent']}%")
    bottom[1].metric("Parked now", data["parked_count"])
    bottom[2].metric("Revenue", money(data["total_revenue"]))
    st.caption(f"{data['completed_sessions']} completed visits.")
    left, right = st.columns(2)
    with left:
        st.subheader("Recent entries")
        if data["recent"]:
            short = history_table(data["recent"])[["Ticket", "Registration", "Type", "Slot", "Status"]]
            st.dataframe(short, hide_index=True, width="stretch")
        else:
            st.info("No vehicles yet.")
    with right:
        st.subheader("Currently parked")
        if not data["activity"]:
            st.info("The lot is empty.")
        for ticket in data["activity"]:
            st.write(f"Slot {ticket.slot_number}: **{ticket.registration_number}** ({ticket.vehicle_type})")
            st.caption(f"{ticket.owner_name} · {ticket.ticket_id} · {show_time(ticket.entry_time)}")


def page_entry(manager):
    st.header("Vehicle Entry")
    st.write("The first free slot is picked for you.")
    with st.form("entry_form", clear_on_submit=True):
        registration = st.text_input("Registration number", placeholder="LEA-4521", key="entry_reg")
        owner = st.text_input("Owner name", placeholder="Ali Khan", key="entry_owner")
        vehicle_type = st.selectbox("Vehicle type", TYPES, key="entry_type")
        day_col, time_col = st.columns(2)
        entry_day = day_col.date_input("Entry date", value=datetime.now().date(), key="entry_date")
        entry_clock = time_col.time_input(
            "Entry time", value=datetime.now().time().replace(second=0, microsecond=0),
            step=timedelta(minutes=1), key="entry_clock",
        )
        submitted = st.form_submit_button("Park vehicle", type="primary", key="entry_submit")
    if submitted:
        try:
            when = datetime.combine(entry_day, entry_clock).replace(second=0, microsecond=0)
            result = manager.register_vehicle(registration, owner, vehicle_type, entry_time=when)
            ticket = result["ticket"]
            st.session_state["last_entry"] = (
                f"{ticket.registration_number} parked in slot {ticket.slot_number}. Ticket {ticket.ticket_id}."
            )
        except ParkingError as exc:
            st.session_state.pop("last_entry", None)
            st.error(str(exc))
    if st.session_state.get("last_entry"):
        st.success(st.session_state["last_entry"])


def page_slots(manager):
    st.header("Parking Slots")
    slots = manager.get_slots()
    free = sum(1 for slot in slots if slot.is_available)
    st.caption(f"{free} free, {len(slots) - free} occupied.")
    for start in range(0, len(slots), 5):
        columns = st.columns(5)
        for column, slot in zip(columns, slots[start:start + 5]):
            with column:
                with st.container(border=True):
                    st.write(f"**Slot {slot.slot_number}**")
                    if slot.is_occupied:
                        st.markdown('<span class="slot-busy">Occupied</span>', unsafe_allow_html=True)
                        st.caption(f"{slot.registration_number} · {slot.vehicle_type}")
                    else:
                        st.markdown('<span class="slot-free">Available</span>', unsafe_allow_html=True)


def page_exit(manager):
    st.header("Vehicle Exit")
    query = st.text_input("Registration or ticket ID", placeholder="LEA-4521 or CP-1001", key="exit_query")
    if st.button("Find vehicle", type="primary", key="exit_find"):
        try:
            st.session_state["exit_ticket_id"] = manager.find_parked(query).ticket_id
        except ParkingError as exc:
            st.session_state.pop("exit_ticket_id", None)
            st.error(str(exc))

    parked = manager.get_history(status="Parked")
    if parked:
        st.caption("Currently inside")
        st.dataframe(history_table(parked), hide_index=True, width="stretch")
    else:
        st.info("No vehicles are parked right now.")

    ticket = None
    if st.session_state.get("exit_ticket_id"):
        try:
            ticket = manager.find_parked(st.session_state["exit_ticket_id"])
        except ParkingError:
            st.session_state.pop("exit_ticket_id", None)
    if not ticket:
        if st.session_state.get("last_receipt"):
            st.success(st.session_state["last_receipt"])
        return

    st.subheader(f"{ticket.registration_number} · {ticket.ticket_id}")
    st.write(f"{ticket.owner_name} · {ticket.vehicle_type} · slot {ticket.slot_number}")
    day_col, time_col = st.columns(2)
    exit_day = day_col.date_input("Exit date", value=datetime.now().date(), key="exit_date")
    exit_clock = time_col.time_input(
        "Exit time", value=datetime.now().time().replace(second=0, microsecond=0),
        step=timedelta(minutes=1), key="exit_clock",
    )
    exit_time = datetime.combine(exit_day, exit_clock).replace(second=0, microsecond=0)
    try:
        bill = manager.preview_fee(ticket, exit_time)
    except ParkingError as exc:
        st.error(str(exc))
        return
    m1, m2, m3 = st.columns(3)
    m1.metric("Duration", bill["duration_text"])
    m2.metric("Billed hours", bill["billable_hours"])
    m3.metric("Total", money(bill["total"]))
    st.write(f"Entry {show_time(bill['entry_time'])} · Exit {show_time(bill['exit_time'])}")
    st.write(f"Rate {money(bill['hourly_rate'])} per hour · {bill['billable_hours']} x {money(bill['hourly_rate'])}")
    st.caption("Minimum charge is 1 hour. A partial hour is rounded up.")
    if st.button("Complete exit", type="primary", key="exit_confirm"):
        try:
            result = manager.exit_vehicle(ticket.ticket_id, exit_time=exit_time)
            st.session_state.pop("exit_ticket_id", None)
            st.session_state["last_receipt"] = (
                f"Exit saved for {result['ticket'].registration_number}. "
                f"Fee {money(result['breakdown']['total'])}. Slot {result['ticket'].slot_number} is free."
            )
            st.rerun()
        except ParkingError as exc:
            st.error(str(exc))


def page_pricing(manager):
    st.header("Pricing")
    rates = manager.get_rates()
    with st.form("pricing_form"):
        columns = st.columns(3)
        edited = {}
        for column, name in zip(columns, TYPES):
            edited[name] = column.number_input(
                f"{name} (PKR / hour)", min_value=1.0, max_value=100000.0,
                value=float(rates.get(name, 1)), step=1.0, key=f"rate_{name}",
            )
        saved = st.form_submit_button("Save rates")
    if saved:
        try:
            rates = manager.update_hourly_rates(edited)
            st.success("Rates saved.")
        except ParkingError as exc:
            st.error(str(exc))
    st.write(
        "Up to 1 hour is charged as 1 hour. 1 hour 20 minutes is charged as 2 hours. "
        f"A car at the current rate would pay {money(2 * float(rates.get('Car', 50)))}."
    )


def page_history(manager):
    st.header("Parking History")
    c1, c2, c3 = st.columns(3)
    search = c1.text_input("Search", key="history_search")
    status = c2.selectbox("Status", ["All", "Parked", "Completed"], key="history_status")
    vehicle_type = c3.selectbox("Type", ["All", *TYPES], key="history_type")
    records = manager.get_history(search=search, status=status, vehicle_type=vehicle_type)
    if not records:
        st.info("Nothing matches.")
        return
    st.dataframe(history_table(records), hide_index=True, width="stretch")


def page_reports(manager):
    st.header("Reports")
    report = manager.get_report()
    a, b, c = st.columns(3)
    a.metric("Completed visits", report["completed_sessions"])
    b.metric("Revenue", money(report["total_revenue"]))
    c.metric("Parked now", report["currently_parked"])
    visits = pd.DataFrame(report["visits_by_type"])
    daily = pd.DataFrame(report["daily_revenue"])
    left, right = st.columns(2)
    with left:
        st.subheader("Visits by type")
        if int(visits["visits"].sum()) == 0:
            st.info("No visits yet.")
        else:
            st.bar_chart(visits, x="vehicle_type", y="visits")
    with right:
        st.subheader("Revenue by day")
        if daily.empty:
            st.info("No payments yet.")
        else:
            st.bar_chart(daily, x="day", y="revenue")
    st.dataframe(pd.DataFrame(report["revenue_by_type"]), hide_index=True, width="stretch")


def main():
    st.set_page_config(page_title="CampusPark", page_icon="P", layout="wide")
    # Just enough colour so free and taken slots are easy to tell apart.
    st.markdown(
        "<style>.slot-free{color:#1B7F4E;font-weight:600}.slot-busy{color:#B42318;font-weight:600}</style>",
        unsafe_allow_html=True,
    )
    try:
        manager = load_manager(db_path())
    except ParkingError as exc:
        st.error(str(exc))
        st.stop()

    st.sidebar.title("CampusPark")
    st.sidebar.caption("Smart Parking. Simplified.")
    page = st.sidebar.radio("Menu", PAGES, label_visibility="collapsed")
    pages = {
        "Dashboard": page_dashboard,
        "Vehicle Entry": page_entry,
        "Parking Slots": page_slots,
        "Vehicle Exit": page_exit,
        "Pricing": page_pricing,
        "Parking History": page_history,
        "Reports": page_reports,
    }
    try:
        pages[page](manager)
    except ParkingError as exc:
        st.error(str(exc))


if __name__ == "__main__":
    main()
