import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.parking_manager import ParkingManager


@pytest.fixture
def manager(tmp_path):
    parking = ParkingManager(tmp_path / "campuspark.db")
    yield parking
    parking.close()
