"""
Tool: process_payment
Pre-validates all card fields locally before calling /api/process-payment.
Tracks payment attempt count — max 3 failures before session termination.
"""
import requests
from agno.agent import Agent as AgnoAgent

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import PROCESS_PAYMENT_ENDPOINT, API_TIMEOUT_SECONDS, PAYMENT_MAX_ATTEMPTS
from validators.card_validator import (
    normalize_card_number,
    validate_card_length,
    luhn_check,
    validate_cvv,
    validate_expiry,
)
from utils.logger import logger 

# Human-readable messages for each API error code
API_ERROR_MESSAGES = {
    "account_not_found": (
        "PAYMENT_FAILED_USER: The provided account ID does not exist. "
        "Ask the user to verify their account details."
    ),
    "insufficient_balance": (
        "PAYMENT_FAILED_USER: The amount exceeds the outstanding balance. "
        "Ask the user to enter an amount within their balance."
    ),
    "invalid_amount": (
        "PAYMENT_FAILED_USER: The payment amount is invalid. "
        "It must be a positive number with up to 2 decimal places."
    ),
    "invalid_card": (
        "PAYMENT_FAILED_USER: The card number is invalid. "
        "Ask the user to re-enter the card number or try a different card."
    ),
    "invalid_cvv": (
        "PAYMENT_FAILED_USER: The CVV is incorrect. "
        "Ask the user to re-enter the CVV or try a different card."
    ),
    "invalid_expiry": (
        "PAYMENT_FAILED_USER: The card expiry is invalid or the card has expired. "
        "Ask the user to check the expiry date or use a different card."
    ),
}


def process_payment(
    agent: AgnoAgent,
    amount: float,
    card_number: str,
    cvv: str,
    expiry_month: int,
    expiry_year: int,
    cardholder_name: str,
) -> str:
    """
    Process a card payment against the account balance.

    Args:
        amount: Payment amount in INR (positive, <= balance, max 2 decimal places).
        card_number: Card number (spaces/dashes are stripped automatically).
        cvv: CVV (3 digits standard, 4 for Amex).
        expiry_month: Expiry month as integer (1-12).
        expiry_year: Full 4-digit expiry year (e.g., 2027).
        cardholder_name: Name as printed on the card.

    Returns:
        A plain-text result the agent uses to form its next response.
    """
    session_id = agent.session_state.get("session_id", "unknown")
    logger.info(f"[{session_id}] PROCESS_PAYMENT initiated for account: {agent.session_state.get('account_id')}")

    def increment_attempt():
        payment_attempts = agent.session_state.get("payment_attempts", 0) + 1
        agent.session_state["payment_attempts"] = payment_attempts
        logger.warning(f"[{session_id}] PROCESS_PAYMENT failed (user error). Attempt {payment_attempts}/{PAYMENT_MAX_ATTEMPTS}")
        if payment_attempts >= PAYMENT_MAX_ATTEMPTS:
            agent.session_state["stage"] = "terminated"
            logger.error(f"[{session_id}] PROCESS_PAYMENT max attempts reached. Session terminated.")
            return True # Terminated
        return False

    # Check if we are already terminated
    payment_attempts = agent.session_state.get("payment_attempts", 0)
    if payment_attempts >= PAYMENT_MAX_ATTEMPTS:
        agent.session_state["stage"] = "terminated"
        return (
            "PAYMENT_FAILED_TERMINAL: Maximum payment attempts reached. "
            "Close the session and advise the user to contact support."
        )

    # ── Pre-validation (before hitting the API) ────────────────────────────
    normalized_card = normalize_card_number(card_number)

    if not validate_card_length(normalized_card):
        terminated = increment_attempt()
        if terminated: return "PAYMENT_FAILED_TERMINAL: Maximum payment attempts reached."
        return (
            f"PAYMENT_VALIDATION_ERROR: Card number has {len(normalized_card)} digits — "
            "expected 13-19. Ask the user to re-enter the card number carefully."
        )

    if not luhn_check(normalized_card):
        terminated = increment_attempt()
        if terminated: return "PAYMENT_FAILED_TERMINAL: Maximum payment attempts reached."
        return (
            "PAYMENT_VALIDATION_ERROR: Card number failed the Luhn check. "
            "Ask the user to double-check the card number."
        )

    if not validate_cvv(cvv, normalized_card):
        expected = 4 if normalized_card.startswith(("34", "37")) else 3
        terminated = increment_attempt()
        if terminated: return "PAYMENT_FAILED_TERMINAL: Maximum payment attempts reached."
        return (
            f"PAYMENT_VALIDATION_ERROR: CVV must be {expected} digits for this card. "
            "Ask the user to re-enter the CVV."
        )

    if not validate_expiry(int(expiry_month), int(expiry_year)):
        terminated = increment_attempt()
        if terminated: return "PAYMENT_FAILED_TERMINAL: Maximum payment attempts reached."
        return (
            "PAYMENT_VALIDATION_ERROR: Card appears expired or the expiry date is invalid. "
            "Ask the user to check the expiry or use a different card."
        )

    # Amount validation
    amount = round(float(amount), 2)
    balance = agent.session_state.get("balance", 0)

    if amount <= 0:
        terminated = increment_attempt()
        if terminated: return "PAYMENT_FAILED_TERMINAL: Maximum payment attempts reached."
        return "PAYMENT_VALIDATION_ERROR: Amount must be greater than zero."

    if amount > balance:
        terminated = increment_attempt()
        if terminated: return "PAYMENT_FAILED_TERMINAL: Maximum payment attempts reached."
        return (
            f"PAYMENT_VALIDATION_ERROR: ₹{amount:.2f} exceeds the outstanding balance "
            f"of ₹{balance:.2f}. Ask the user for a lower amount."
        )

    account_id = agent.session_state.get("account_id")

    payload = {
        "account_id": account_id,
        "amount": amount,
        "payment_method": {
            "type": "card",
            "card": {
                "cardholder_name": cardholder_name,
                "card_number": normalized_card,
                "cvv": str(cvv),
                "expiry_month": int(expiry_month),
                "expiry_year": int(expiry_year),
            },
        },
    }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.Timeout, requests.ConnectionError)),
        reraise=True
    )
    def _do_payment():
        return requests.post(
            PROCESS_PAYMENT_ENDPOINT, json=payload, timeout=API_TIMEOUT_SECONDS
        )

    try:
        response = _do_payment()

        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                txn_id = data.get("transaction_id")
                agent.session_state["payment_done"] = True
                agent.session_state["transaction_id"] = txn_id
                agent.session_state["stage"] = "done"
                logger.info(f"[{session_id}] PROCESS_PAYMENT success! Txn ID: {txn_id}")
                return (
                    f"PAYMENT_SUCCESS: ₹{amount:.2f} processed. "
                    f"Transaction ID: {txn_id}. "
                    "Confirm payment to the user and close the conversation warmly."
                )

        if response.status_code in (400, 422):
            terminated = increment_attempt()
            error_code = response.json().get("error_code", "unknown")
            logger.warning(f"[{session_id}] PROCESS_PAYMENT API rejected (user error): {error_code}")
            if terminated: return "PAYMENT_FAILED_TERMINAL: Maximum payment attempts reached."
            return API_ERROR_MESSAGES.get(
                error_code,
                f"PAYMENT_FAILED_USER: Payment failed (error: {error_code}). "
                "Ask the user to check their card details or try a different card.",
            )

        # 500s or unexpected errors: Do NOT increment attempt
        logger.error(f"[{session_id}] PROCESS_PAYMENT unexpected HTTP {response.status_code}")
        return (
            f"PAYMENT_FAILED_UNEXPECTED: Payment service returned HTTP {response.status_code}. "
            "Inform the user and suggest contacting support. Do not ask for another attempt."
        )

    except requests.Timeout:
        logger.error(f"[{session_id}] PROCESS_PAYMENT timed out after retries.")
        return (
            "PAYMENT_FAILED_RETRYABLE: Payment service timed out. "
            "Ask the user if they'd like to try again."
        )
    except requests.ConnectionError:
        logger.error(f"[{session_id}] PROCESS_PAYMENT connection error after retries.")
        return (
            "PAYMENT_FAILED_RETRYABLE: Cannot reach the payment service. "
            "Ask the user to try again in a moment."
        )
    except Exception as e:
        logger.exception(f"[{session_id}] PROCESS_PAYMENT unexpected error: {e}")
        return f"PAYMENT_FAILED_UNEXPECTED: Unexpected error: {e}. Please try again."
