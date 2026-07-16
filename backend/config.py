import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "outputs"
STATIC_DIR = BASE_DIR / "static" / "generated"

POLLINATIONS_KEY = os.environ.get("POLLINATIONS_KEY", "sk_qGTE6yG58UawexsyAcoQwpi0CDGWaF2o")
POLLINATIONS_PK = os.environ.get("POLLINATIONS_PK", "pk_j1VCcxAp2GYeMzyx")
HF_TOKEN = os.environ.get("HF_TOKEN", "")

CLOUDINARY_CLOUD = os.environ.get("CLOUDINARY_CLOUD", "cm4h85pv")
CLOUDINARY_KEY = os.environ.get("CLOUDINARY_KEY", "344499215755811")
CLOUDINARY_SECRET = os.environ.get("CLOUDINARY_SECRET", "YlDFDkUqeYhf0cl5HZvKpTgB04w")

CRYPTOBOT_TOKEN = os.environ.get("CRYPTOBOT_TOKEN", "")
CRYPTOBOT_WEBHOOK_SECRET = os.environ.get("CRYPTOBOT_WEBHOOK_SECRET", "vdai_secret_" + secrets.token_hex(8))

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)
