"""Open each page, then park one vehicle through the form."""

import html
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app.py"
PAGES = [
    "Dashboard",
    "Vehicle Entry",
    "Parking Slots",
    "Vehicle Exit",
    "Pricing",
    "Parking History",
    "Reports",
]


def _text(app):
    widgets = (
        list(app.title) + list(app.header) + list(app.subheader)
        + list(app.markdown) + list(app.caption)
        + list(app.success) + list(app.info) + list(app.error)
    )
    return html.unescape("\n".join(str(item.value) for item in widgets))


def _ok(app):
    assert not app.exception, app.exception


def test_every_page_opens(tmp_path, monkeypatch):
    monkeypatch.setenv("CAMPUSPARK_DB", str(tmp_path / "smoke.db"))
    app = AppTest.from_file(str(APP), default_timeout=60)
    app.run()
    _ok(app)
    for page in PAGES:
        app.sidebar.radio[0].set_value(page).run()
        _ok(app)
        assert page in _text(app)


def test_entry_form_parks_a_vehicle(tmp_path, monkeypatch):
    monkeypatch.setenv("CAMPUSPARK_DB", str(tmp_path / "entry.db"))
    app = AppTest.from_file(str(APP), default_timeout=60)
    app.run()
    app.sidebar.radio[0].set_value("Vehicle Entry").run()
    app.text_input(key="entry_reg").set_value("LEA-4521")
    app.text_input(key="entry_owner").set_value("Ali Khan")
    app.button(key="entry_submit").click().run()
    _ok(app)
    assert "CP-1001" in _text(app)
