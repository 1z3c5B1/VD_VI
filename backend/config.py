import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "outputs"
STATIC_DIR = BASE_DIR / "static" / "generated"

POLLINATIONS_KEY = os.environ.get("POLLINATIONS_KEY", "sk_qGTE6yG58UawexsyAcoQwpi0CDGWaF2o")
POLLINATIONS_PK = os.environ.get("POLLINATIONS_PK", "pk_j1VCcxAp2GYeMzyx")
HF_TOKEN = os.environ.get("HF_TOKEN", "")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)
