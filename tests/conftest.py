import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.billing_manager import BillingManager


@pytest.fixture
def manager(tmp_path):
    billing = BillingManager(tmp_path / "billing.db")
    yield billing
    billing.close()
