"""Headless Streamlit checks. No browser window is opened.

AppTest runs app.py the way Streamlit does and records the widgets.
"""

import html
import os
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_FILE = Path(__file__).resolve().parents[1] / "app.py"
PAGES = [
    "Dashboard",
    "Vehicle Entry",
    "Parking Slots",
    "Vehicle Exit",
    "Pricing",
    "Parking History",
    "Reports & Analytics",
]


def _assert_clean(app):
    if not app.exception:
        return
    details = []
    for problem in app.exception:
        details.append(getattr(problem, "value", None) or getattr(problem, "message", None) or str(problem))
    raise AssertionError("Streamlit page raised: " + " | ".join(details))


def _page_text(app):
    chunks = []
    for widget in app.markdown:
        chunks.append(str(widget.value))
    for widget in app.success:
        chunks.append(str(widget.value))
    for widget in app.info:
        chunks.append(str(widget.value))
    for widget in app.error:
        chunks.append(str(widget.value))
    return html.unescape("\n".join(chunks))


def test_every_page_renders(tmp_path, monkeypatch):
    monkeypatch.setenv("CAMPUSPARK_DB", str(tmp_path / "smoke.db"))
    monkeypatch.setenv("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")
    # The path is read when the script runs, not when this assertion is imported.
    assert os.environ["CAMPUSPARK_DB"].endswith("smoke.db")

    app = AppTest.from_file(str(APP_FILE), default_timeout=60)
    app.run()
    _assert_clean(app)
    assert "CampusPark" in _page_text(app)
    assert "Dashboard" in _page_text(app)

    for page in PAGES:
        app.sidebar.radio[0].set_value(page).run()
        _assert_clean(app)
        assert page in _page_text(app)


def test_entry_page_parks_a_vehicle(tmp_path, monkeypatch):
    monkeypatch.setenv("CAMPUSPARK_DB", str(tmp_path / "entry.db"))
    monkeypatch.setenv("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")

    app = AppTest.from_file(str(APP_FILE), default_timeout=60)
    app.run()
    app.sidebar.radio[0].set_value("Vehicle Entry").run()
    _assert_clean(app)

    app.text_input(key="entry_reg").set_value("LEA-4521")
    app.text_input(key="entry_owner").set_value("Ali Khan")
    app.selectbox(key="entry_type").set_value("Car")
    app.button(key="entry_submit").click().run()
    _assert_clean(app)

    text = _page_text(app)
    assert "CP-1001" in text
    assert "LEA-4521" in text

    app.sidebar.radio[0].set_value("Parking Slots").run()
    _assert_clean(app)
    slots_text = _page_text(app)
    assert "Occupied" in slots_text
    assert "LEA-4521" in slots_text
