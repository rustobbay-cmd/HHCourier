from dotenv import load_dotenv
import os

load_dotenv()

COURIER_BOT_TOKEN = os.getenv("COURIER_BOT_TOKEN")
CAFE_ADMIN_IDS = [int(i) for i in os.getenv("CAFE_ADMIN_IDS").split(",")]
CAFE_DB_PATH = os.getenv("CAFE_DB_PATH")
