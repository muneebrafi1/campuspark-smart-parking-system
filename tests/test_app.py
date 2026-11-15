"""Open every page of the billing app."""

import html
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app.py"
PAGES = ["Dashboard", "Customers", "Meter Readings", "Bills", "Tariff", "Bill History"]


def _text(app):
    widgets = list(app.title) + list(app.header) + list(app.subheader) + list(app.markdown) + list(app.info)
    return html.unescape("\n".join(str(item.value) for item in widgets))


def test_every_page_opens(tmp_path, monkeypatch):
    monkeypatch.setenv("BILLING_DB", str(tmp_path / "ui.db"))
    app = AppTest.from_file(str(APP), default_timeout=60)
    app.run()
    assert not app.exception
    for page in PAGES:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception, app.exception
        assert page in _text(app)
