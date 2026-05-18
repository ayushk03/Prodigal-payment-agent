"""
Tool: lookup_account
Calls /api/lookup-account and stores account data in Agno session state.
The LLM never sees DOB, Aadhaar, or pincode — they live only in session_state.
"""
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from agno.agent import Agent as AgnoAgent

from config import LOOKUP_ACCOUNT_ENDPOINT, API_TIMEOUT_SECONDS
from utils.logger import logger


def lookup_account(agent: AgnoAgent, account_id: str) -> str:
    """
    Look up a user account by ID.

    Args:
        account_id: Account identifier provided by the user (e.g. 'ACC1001').

    Returns:
        A plain-text result the agent uses to form its next response.
    """
    normalized_id = account_id.strip().upper().replace(" ", "")
    session_id = agent.session_state.get("session_id", "unknown")

    logger.info(f"[{session_id}] LOOKUP_ACCOUNT initiated for ID: {normalized_id}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.Timeout, requests.ConnectionError)),
        reraise=True
    )
    def _do_request():
        return requests.post(
            LOOKUP_ACCOUNT_ENDPOINT,
            json={"account_id": normalized_id},
            timeout=API_TIMEOUT_SECONDS,
        )

    try:
        response = _do_request()
        
        if response.status_code == 200:
            data = response.json()
            # Store full account data — never returned to the LLM directly
            agent.session_state["account_id"] = normalized_id
            agent.session_state["account_found"] = True
            agent.session_state["account_data"] = data
            agent.session_state["balance"] = data["balance"]
            agent.session_state["stage"] = "verify"
            
            logger.info(f"[{session_id}] LOOKUP_ACCOUNT success for {normalized_id}")
            return (
                f"Account found for {normalized_id}. "
                "Now ask the user for their full name and one secondary factor "
                "(date of birth, Aadhaar last 4 digits, or pincode). "
                "Do NOT share balance or any account details yet."
            )

        if response.status_code == 404:
            logger.warning(f"[{session_id}] LOOKUP_ACCOUNT failed: 404 Not Found for {normalized_id}")
            return (
                f"No account found with ID '{normalized_id}'. "
                "Ask the user to double-check and re-enter their account ID."
            )

        logger.error(f"[{session_id}] LOOKUP_ACCOUNT unexpected HTTP {response.status_code}")
        return (
            f"Account service returned an unexpected error (HTTP {response.status_code}). "
            "Ask the user to try again."
        )

    except requests.Timeout:
        logger.error(f"[{session_id}] LOOKUP_ACCOUNT timed out after retries.")
        return "Account service timed out. Ask the user to try again in a moment."
    except requests.ConnectionError:
        logger.error(f"[{session_id}] LOOKUP_ACCOUNT connection error after retries.")
        return "Cannot reach the account service. Ask the user to try again later."
    except Exception as e:
        logger.exception(f"[{session_id}] LOOKUP_ACCOUNT unexpected error: {e}")
        return f"Unexpected error during account lookup: {e}. Please try again."
