"""CampusPark — the Streamlit desk screen.

This file draws the pages. The rules (who may enter, which slot they
get, and what they pay) live in the classes under models/ and services/.
The SQL lives in database/database_manager.py.

Run from the project folder:

    streamlit run app.py
"""

import html
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from services.parking_manager import ParkingManager
from utils.exceptions import ParkingError
from utils.helpers import (
    VEHICLE_TYPES,
    combine_date_and_time,
    format_display_time,
    format_duration,
    format_money,
    status_label,
)

APP_NAME = "CampusPark"
APP_TAGLINE = "Smart Parking. Simplified."
PAGES = [
    "Dashboard",
    "Vehicle Entry",
    "Parking Slots",
    "Vehicle Exit",
    "Pricing",
    "Parking History",
    "Reports & Analytics",
]


def database_path():
    """SQLite file. Tests can point CAMPUSPARK_DB at a temporary file."""
    configured = os.environ.get("CAMPUSPARK_DB")
    if configured:
        return configured
    return str(ROOT / "data" / "campuspark.db")


@st.cache_resource
def load_manager(db_path):
    """One manager for the whole Streamlit process.

    Caching matters: a new manager on every click would be wasteful, and
    the open SQLite connection stays tied to this object. Data is still
    read from the file on each action, so a refresh shows the saved rows.
    """
    return ParkingManager(db_path)


def inject_theme():
    css_path = ROOT / "assets" / "style.css"
    css = css_path.read_text(encoding="utf-8") if css_path.exists() else ""
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def show_html(source, sidebar=False):
    """Render HTML.

    Streamlit's Markdown treats a 4-space indent as a code block, so every
    line is left-aligned before it is sent to the page.
    """
    cleaned = "\n".join(line.lstrip() for line in source.splitlines()).strip()
    target = st.sidebar if sidebar else st
    target.markdown(cleaned, unsafe_allow_html=True)


def brand_mark():
    logo_path = ROOT / "assets" / "logo.svg"
    logo = logo_path.read_text(encoding="utf-8") if logo_path.exists() else ""
    show_html(
        f"""
        <div class="brand-row">
            {logo}
            <div>
                <p class="brand-name">{APP_NAME}</p>
                <p class="brand-tag">{APP_TAGLINE}</p>
            </div>
        </div>
        <p class="menu-label">MENU</p>
        """,
        sidebar=True,
    )


def page_header(title, subtitle):
    show_html(
        f"""
        <div class="page-head">
            <p class="eyebrow">{APP_NAME.upper()}</p>
            <h1>{html.escape(title)}</h1>
            <p class="subtitle">{html.escape(subtitle)}</p>
        </div>
        """
    )


def panel(title, body_html):
    show_html(
        f"""
        <div class="panel">
            <h3>{html.escape(title)}</h3>
            {body_html}
        </div>
        """
    )


def selected_page():
    """Sidebar navigation. A ?page= link can open a page directly."""
    if "nav_page" not in st.session_state:
        requested = st.query_params.get("page", PAGES[0])
        st.session_state.nav_page = requested if requested in PAGES else PAGES[0]
    page = st.sidebar.radio("Go to", PAGES, key="nav_page", label_visibility="collapsed")
    if st.query_params.get("page") != page:
        st.query_params["page"] = page
    return page


def go_to(page_name):
    st.session_state.nav_page = page_name
    st.rerun()


def present_breakdown(breakdown):
    return {
        "entry_time": format_display_time(breakdown["entry_time"]),
        "exit_time": format_display_time(breakdown["exit_time"]),
        "duration_text": breakdown["duration_text"],
        "billable_hours": str(breakdown["billable_hours"]),
        "hourly_rate": format_money(breakdown["hourly_rate"]),
        "total_amount": format_money(breakdown["total_amount"]),
        "math": (
            f"{breakdown['billable_hours']} × {format_money(breakdown['hourly_rate'])} "
            f"= {format_money(breakdown['total_amount'])}"
        ),
        "policy": breakdown["policy"],
        "vehicle_type": breakdown["vehicle_type"],
    }


def render_breakdown(presented):
    show_html(
        f"""
        <div class="receipt">
            <div>
                <p class="label">Entry</p>
                <p class="value">{html.escape(presented["entry_time"])}</p>
            </div>
            <div>
                <p class="label">Exit</p>
                <p class="value">{html.escape(presented["exit_time"])}</p>
            </div>
            <div>
                <p class="label">Duration</p>
                <p class="value">{html.escape(presented["duration_text"])}</p>
            </div>
            <div>
                <p class="label">Billable hours</p>
                <p class="value">{html.escape(presented["billable_hours"])}</p>
            </div>
            <div>
                <p class="label">Hourly rate</p>
                <p class="value">{html.escape(presented["hourly_rate"])}</p>
            </div>
            <div>
                <p class="label">Vehicle</p>
                <p class="value">{html.escape(presented["vehicle_type"])}</p>
            </div>
            <div class="total">
                <p class="label">Total amount</p>
                <p class="value">{html.escape(presented["total_amount"])}</p>
                <p class="label">{html.escape(presented["math"])}</p>
            </div>
        </div>
        """
    )
    st.caption(presented["policy"])


def format_table_time(value):
    """Shorter than the receipt clock so the history table fits on one screen."""
    if value is None:
        return "—"
    return value.strftime("%d %b %H:%M")


def history_frame(records, columns=None):
    """Table rows for history and the dashboard. Parked visits have no fee yet."""
    now = datetime.now()
    rows = []
    for record in records:
        if record["status"] == "parked":
            if now >= record["entry_time"]:
                duration = format_duration(now - record["entry_time"])
            else:
                duration = "—"
            exit_label = "—"
            billable = "—"
            fee = "—"
        else:
            duration = record["duration_text"] or "—"
            exit_label = format_display_time(record["exit_time"])
            billable = record["billable_hours"]
            fee = format_money(record["fee"])
        rows.append(
            {
                "Ticket ID": record["ticket_id"],
                "Registration": record["registration_number"],
                "Owner": record["owner_name"],
                "Type": record["vehicle_type"],
                "Slot": int(record["slot_number"]),
                "Entry": format_table_time(record["entry_time"]),
                "Exit": exit_label if exit_label == "—" else format_table_time(record["exit_time"]),
                "Duration": duration,
                "Billable hours": billable,
                "Fee": fee,
                "Status": status_label(record["status"]),
            }
        )
    frame = pd.DataFrame(rows)
    if columns:
        frame = frame[columns]
    return frame


def show_table(frame):
    """A compact table. A dataframe's last column was getting cut off."""
    if frame is None or frame.empty:
        return
    headers = "".join(f"<th>{html.escape(str(column))}</th>" for column in frame.columns)
    body_rows = []
    for row in frame.itertuples(index=False):
        cells = "".join(f"<td>{html.escape(str(value))}</td>" for value in row)
        body_rows.append(f"<tr>{cells}</tr>")
    show_html(
        '<div class="table-wrap"><table class="data-table">'
        f"<thead><tr>{headers}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody></table></div>"
    )


def render_dashboard(manager):
    page_header("Dashboard", "A live picture of the campus lot, from the saved records.")
    try:
        data = manager.get_dashboard()
    except ParkingError as exc:
        st.error(str(exc))
        return

    occupancy = data["occupancy_percent"]
    occupancy_text = f"{int(occupancy)}%" if float(occupancy).is_integer() else f"{occupancy:.1f}%"

    first = st.columns(3)
    first[0].metric("Total spaces", data["total_slots"])
    first[1].metric("Available", data["available"])
    first[2].metric("Occupied", data["occupied"])
    second = st.columns(3)
    second[0].metric("Occupancy", occupancy_text)
    second[1].metric("Vehicles parked", data["parked_count"])
    second[2].metric("Total revenue", format_money(data["total_revenue"]))

    ratio = (data["occupied"] / data["total_slots"]) if data["total_slots"] else 0
    st.progress(ratio, text=f"{data['occupied']} of {data['total_slots']} slots in use")
    st.caption(
        f"{data['completed_sessions']} completed "
        f"{'session' if data['completed_sessions'] == 1 else 'sessions'} "
        "have been paid and stored."
    )

    left, right = st.columns([1.3, 1])
    with left:
        st.subheader("Recent entries")
        if data["recent"]:
            show_table(
                history_frame(
                    data["recent"],
                    columns=["Ticket ID", "Registration", "Type", "Slot", "Entry", "Status"],
                )
            )
        else:
            st.info("No vehicles have entered yet.")
            if st.button("Register the first vehicle", key="dash_to_entry"):
                go_to("Vehicle Entry")
    with right:
        st.subheader("Current activity")
        if not data["activity"]:
            st.info("The lot is empty right now.")
        for ticket in data["activity"]:
            parked_for = "—"
            if datetime.now() >= ticket.entry_time:
                parked_for = format_duration(datetime.now() - ticket.entry_time)
            with st.container(border=True):
                st.markdown(
                    f"**Slot {ticket.slot_number:02d}** · {ticket.registration_number}  \n"
                    f"{ticket.owner_name} · {ticket.vehicle_type}  \n"
                    f"In since {format_display_time(ticket.entry_time)} · {parked_for}"
                )


def render_entry(manager):
    page_header("Vehicle Entry", "Check the vehicle in. The first free slot is assigned for you.")
    form_col, help_col = st.columns([1.25, 0.85])
    with help_col:
        panel(
            "What happens on entry",
            """
            <ol>
                <li>The registration number is checked and stored in one format.</li>
                <li>A vehicle that is already inside is rejected.</li>
                <li>The lowest free slot number is reserved.</li>
                <li>A ticket ID such as CP-1001 is created and saved.</li>
            </ol>
            <p>If all 20 slots are full, the vehicle is not admitted.</p>
            """,
        )
        panel(
            "Entry time",
            """
            <p>Leave the clock as it is for a real arrival. Set an earlier
            time when you want to demonstrate a longer stay at the exit desk.</p>
            """,
        )

    with form_col:
        with st.form("entry_form", clear_on_submit=True):
            registration = st.text_input(
                "Registration number",
                placeholder="LEA-4521",
                key="entry_reg",
            )
            owner = st.text_input(
                "Owner name",
                placeholder="Ali Khan",
                key="entry_owner",
            )
            vehicle_type = st.selectbox("Vehicle type", VEHICLE_TYPES, key="entry_type")
            date_col, time_col = st.columns(2)
            entry_day = date_col.date_input("Entry date", value=datetime.now().date(), key="entry_date")
            entry_clock = time_col.time_input(
                "Entry time",
                value=datetime.now().time().replace(second=0, microsecond=0),
                step=timedelta(minutes=1),
                key="entry_clock",
            )
            submitted = st.form_submit_button(
                "Park vehicle",
                type="primary",
                width="stretch",
                key="entry_submit",
            )

        if submitted:
            try:
                result = manager.register_vehicle(
                    registration,
                    owner,
                    vehicle_type,
                    entry_time=combine_date_and_time(entry_day, entry_clock),
                )
                ticket = result["ticket"]
                st.session_state["last_entry"] = {
                    "message": result["message"],
                    "ticket_id": ticket.ticket_id,
                    "registration_number": ticket.registration_number,
                    "owner_name": ticket.owner_name,
                    "vehicle_type": ticket.vehicle_type,
                    "slot_number": ticket.slot_number,
                    "entry_time": format_display_time(ticket.entry_time),
                    "description": result["vehicle"].get_description(),
                }
                st.toast("Vehicle parked")
            except ParkingError as exc:
                st.session_state.pop("last_entry", None)
                st.error(str(exc))

    last = st.session_state.get("last_entry")
    if last:
        st.success(last["message"])
        panel(
            f"Ticket {last['ticket_id']}",
            f"""
            <p><strong>{html.escape(last["registration_number"])}</strong>
            · {html.escape(last["owner_name"])}</p>
            <p>{html.escape(last["description"])}</p>
            <p>Slot {int(last["slot_number"]):02d} · arrived {html.escape(last["entry_time"])}</p>
            """,
        )


def render_slots(manager):
    page_header("Parking Slots", "Green is free. Red is taken. The board updates after every entry and exit.")
    try:
        slots = manager.get_slots()
    except ParkingError as exc:
        st.error(str(exc))
        return

    free = sum(1 for slot in slots if slot.is_available)
    busy = len(slots) - free
    metric_cols = st.columns(3)
    metric_cols[0].metric("Total slots", len(slots))
    metric_cols[1].metric("Available", free)
    metric_cols[2].metric("Occupied", busy)
    show_html(
        """
        <div class="slot-legend">
            <span><i class="dot dot-free"></i>Available</span>
            <span><i class="dot dot-busy"></i>Occupied</span>
        </div>
        """
    )

    cards = []
    for slot in slots:
        if slot.is_occupied:
            kind = "busy"
            state = "Occupied"
            meta = (
                f"{html.escape(slot.registration_number or '')}<br>"
                f"{html.escape(slot.vehicle_type or '')}"
            )
        else:
            kind = "free"
            state = "Available"
            meta = "Open"
        cards.append(
            "<div class=\"slot-card " + kind + "\">"
            f"<div class=\"slot-num\">Slot {slot.slot_number:02d}</div>"
            f"<div class=\"slot-status\">{state}</div>"
            f"<div class=\"slot-meta\">{meta}</div>"
            "</div>"
        )
    show_html(f'<div class="slot-grid">{"".join(cards)}</div>')


def render_exit(manager):
    page_header("Vehicle Exit", "Find the visit, check the bill, then release the slot.")
    try:
        parked = manager.get_active_tickets()
    except ParkingError as exc:
        st.error(str(exc))
        return

    query = st.text_input(
        "Registration number or ticket ID",
        placeholder="LEA-4521 or CP-1001",
        key="exit_query",
    )
    if st.button("Find vehicle", type="primary", key="exit_find"):
        try:
            ticket = manager.find_parked(query)
            st.session_state["exit_ticket_id"] = ticket.ticket_id
        except ParkingError as exc:
            st.session_state.pop("exit_ticket_id", None)
            st.error(str(exc))

    if parked:
        st.caption("Currently inside")
        show_table(
            history_frame(
                [
                    {
                        "ticket_id": ticket.ticket_id,
                        "registration_number": ticket.registration_number,
                        "owner_name": ticket.owner_name,
                        "vehicle_type": ticket.vehicle_type,
                        "slot_number": ticket.slot_number,
                        "entry_time": ticket.entry_time,
                        "exit_time": None,
                        "duration_text": None,
                        "billable_hours": None,
                        "hourly_rate": None,
                        "fee": None,
                        "status": ticket.status,
                    }
                    for ticket in parked
                ],
                columns=["Ticket ID", "Registration", "Owner", "Type", "Slot", "Entry"],
            )
        )
    else:
        st.info("No vehicles are parked right now.")

    ticket_id = st.session_state.get("exit_ticket_id")
    ticket = None
    if ticket_id:
        try:
            ticket = manager.find_parked(ticket_id)
        except ParkingError:
            st.session_state.pop("exit_ticket_id", None)

    if ticket is not None:
        st.subheader(f"{ticket.registration_number} · {ticket.ticket_id}")
        st.write(
            f"{ticket.owner_name} · {ticket.vehicle_type} · slot {ticket.slot_number:02d} · "
            f"entered {format_display_time(ticket.entry_time)}"
        )
        date_col, time_col = st.columns(2)
        exit_day = date_col.date_input("Exit date", value=datetime.now().date(), key="exit_date")
        exit_clock = time_col.time_input(
            "Exit time",
            value=datetime.now().time().replace(second=0, microsecond=0),
            step=timedelta(minutes=1),
            key="exit_clock",
        )
        exit_time = combine_date_and_time(exit_day, exit_clock)
        preview = None
        try:
            preview = present_breakdown(manager.preview_fee(ticket, exit_time))
            render_breakdown(preview)
        except ParkingError as exc:
            st.error(str(exc))

        if preview and st.button("Complete exit and release slot", type="primary", key="exit_confirm"):
            try:
                result = manager.exit_vehicle(ticket.ticket_id, exit_time=exit_time)
                st.session_state.pop("exit_ticket_id", None)
                st.session_state["last_receipt"] = {
                    "message": result["message"],
                    "ticket_id": result["ticket"].ticket_id,
                    "registration_number": result["ticket"].registration_number,
                    "slot_number": result["ticket"].slot_number,
                    "presented": present_breakdown(result["breakdown"]),
                }
                st.toast("Exit saved")
                st.rerun()
            except ParkingError as exc:
                st.error(str(exc))

    receipt = st.session_state.get("last_receipt")
    if receipt:
        st.success(receipt["message"])
        st.markdown(f"**Receipt {html.escape(receipt['ticket_id'])}**")
        render_breakdown(receipt["presented"])


def render_pricing(manager):
    page_header("Pricing", "Set the hourly rate for each vehicle type. The next exit uses the new rate.")
    try:
        rates = manager.get_rates()
    except ParkingError as exc:
        st.error(str(exc))
        return

    with st.form("pricing_form"):
        columns = st.columns(3)
        edited = {}
        for column, vehicle_type in zip(columns, VEHICLE_TYPES):
            edited[vehicle_type] = column.number_input(
                f"{vehicle_type} (PKR per hour)",
                min_value=1.0,
                max_value=100000.0,
                value=float(rates.get(vehicle_type, 1)),
                step=1.0,
                key=f"rate_{vehicle_type}",
            )
        saved = st.form_submit_button("Save pricing", type="primary")

    if saved:
        try:
            manager.update_hourly_rates(edited)
            st.success("Hourly rates saved. They apply the next time a vehicle exits.")
            st.toast("Pricing saved")
            rates = manager.get_rates()
        except ParkingError as exc:
            st.error(str(exc))

    car_rate = float(rates.get("Car", 50))
    panel(
        "How the bill is rounded",
        f"""
        <ul>
            <li>The minimum charge is <strong>1 hour</strong>, even for a very short stay.</li>
            <li>A partial hour is <strong>rounded up</strong>. 1 hour 1 minute is billed as 2 hours.</li>
            <li>An exact number of hours stays exact. 2 hours is billed as 2 hours.</li>
            <li>The rate in force at exit time is the rate that is charged.</li>
        </ul>
        <p>Example with the current car rate: 1 hour 20 minutes is
        2 × {html.escape(format_money(car_rate))} =
        <strong>{html.escape(format_money(2 * car_rate))}</strong>.</p>
        """,
    )
    current = pd.DataFrame(
        [{"Vehicle": name, "Hourly rate": format_money(rates.get(name))} for name in VEHICLE_TYPES]
    )
    show_table(current)


def render_history(manager):
    page_header("Parking History", "Every visit that was saved. Search by ticket, registration, or owner.")
    filters = st.columns([1.4, 1, 1])
    search = filters[0].text_input("Search", placeholder="CP-1001, LEA-4521, or a name", key="history_search")
    status = filters[1].selectbox("Status", ["All", "Parked", "Completed"], key="history_status")
    vehicle_type = filters[2].selectbox("Vehicle type", ["All", *VEHICLE_TYPES], key="history_type")

    try:
        records = manager.get_history(search=search, status=status, vehicle_type=vehicle_type)
    except ParkingError as exc:
        st.error(str(exc))
        return

    st.caption(f"{len(records)} {'visit' if len(records) == 1 else 'visits'}")
    if not records:
        st.info("No visits match this search.")
        return

    frame = history_frame(records)
    show_table(frame)
    st.download_button(
        "Download this list as CSV",
        data=frame.to_csv(index=False).encode("utf-8"),
        file_name="campuspark-history.csv",
        mime="text/csv",
        key="history_download",
    )


def render_reports(manager):
    page_header("Reports & Analytics", "Completed stays, money collected, and how the lot is used.")
    try:
        report = manager.get_report()
    except ParkingError as exc:
        st.error(str(exc))
        return

    columns = st.columns(3)
    columns[0].metric("Completed sessions", report["completed_sessions"])
    columns[1].metric("Total revenue", format_money(report["total_revenue"]))
    columns[2].metric("Currently parked", report["currently_parked"])

    visits = pd.DataFrame(report["visits_by_type"])
    daily = pd.DataFrame(report["daily_revenue"])
    by_type = pd.DataFrame(report["revenue_by_type"])

    chart_left, chart_right = st.columns(2)
    with chart_left:
        st.subheader("Visits by vehicle type")
        if int(visits["visits"].sum()) == 0:
            st.info("No visits have been recorded yet.")
        else:
            st.bar_chart(visits, x="vehicle_type", y="visits")
    with chart_right:
        st.subheader("Revenue by day")
        if daily.empty:
            st.info("Revenue appears here after the first exit.")
        else:
            st.bar_chart(daily, x="day", y="revenue")

    st.subheader("Revenue by vehicle type")
    display = by_type.copy()
    display["revenue"] = display["revenue"].map(format_money)
    display = display.rename(
        columns={
            "vehicle_type": "Vehicle",
            "revenue": "Revenue",
            "sessions": "Paid sessions",
        }
    )
    show_table(display)


def render_footer():
    show_html(
        "<p class=\"app-footer\">CampusPark · Smart Parking. Simplified. · "
        "Records are stored in a local SQLite file and stay there when you change pages.</p>"
    )


def main():
    st.set_page_config(
        page_title=APP_NAME,
        page_icon="🅿️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_theme()
    try:
        manager = load_manager(database_path())
    except ParkingError as exc:
        st.error(str(exc))
        st.stop()

    brand_mark()
    try:
        slots = manager.get_slots()
        free = sum(1 for slot in slots if slot.is_available)
        st.sidebar.caption(f"{free} of {len(slots)} slots free")
    except ParkingError:
        st.sidebar.caption("Slot count unavailable")
    st.sidebar.caption(datetime.now().strftime("%d %b %Y · %I:%M %p"))

    page = selected_page()
    pages = {
        "Dashboard": render_dashboard,
        "Vehicle Entry": render_entry,
        "Parking Slots": render_slots,
        "Vehicle Exit": render_exit,
        "Pricing": render_pricing,
        "Parking History": render_history,
        "Reports & Analytics": render_reports,
    }
    pages[page](manager)
    render_footer()


if __name__ == "__main__":
    main()
