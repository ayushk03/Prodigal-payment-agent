"""
Central configuration for the Payment Collection Agent.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── API ───────────────────────────────────────────────────────────────────────
API_BASE_URL = "https://se-payment-verification-api.service.external.usea2.aws.prodigaltech.com"
LOOKUP_ACCOUNT_ENDPOINT = f"{API_BASE_URL}/api/lookup-account"
PROCESS_PAYMENT_ENDPOINT = f"{API_BASE_URL}/api/process-payment"
API_TIMEOUT_SECONDS = 10

# ── LLM ───────────────────────────────────────────────────────────────────────
GEMINI_MODEL_ID = "gemini-3.1-flash-lite"
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
MAX_TOKENS = 1024                                 # max tokens per agent response

# ── Agent limits ──────────────────────────────────────────────────────────────
VERIFICATION_MAX_ATTEMPTS = 3   # failed verify attempts before session termination
PAYMENT_MAX_ATTEMPTS = 3        # failed payment attempts before session termination

# ── Storage ───────────────────────────────────────────────────────────────────
SQLITE_DB_FILE = "data/sessions.db"
NUM_HISTORY_RUNS = 50           # conversation turns kept in context
