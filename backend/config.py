import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "outputs"
STATIC_DIR = BASE_DIR / "static" / "generated"

POLLINATIONS_KEY = os.environ.get("POLLINATIONS_KEY", "sk_TxyHaOVGAzdSY8FIk1bRoAN6dA47TBuO")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)
