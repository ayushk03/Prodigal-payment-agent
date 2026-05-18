"""
Tool: verify_user
Pure Python — no external API.
Hard verification: full name must match exactly + at least one secondary factor.
Called by the LLM once it has collected name + at least one of DOB/Aadhaar last 4/pincode.
"""
from typing import Optional

from agno.agent import Agent as AgnoAgent

from config import VERIFICATION_MAX_ATTEMPTS
from validators.date_validator import validate_date


def verify_user(
    agent: AgnoAgent,
    name: str,
    dob: Optional[str] = None,
    aadhaar_last4: Optional[str] = None,
    pincode: Optional[str] = None,
) -> str:
    """
    Verify user identity against account data retrieved during account lookup.

    Verification rule:
        PASS if: (name == stored_name) AND at least one of (dob / aadhaar_last4 / pincode) matches.
        FAIL otherwise — increments the attempt counter each time.

    Args:
        name:          Full name as interpreted from user input (e.g. "Nithin Jain").
        dob:           Date of birth normalized to YYYY-MM-DD (e.g. "1990-05-14"). Optional.
        aadhaar_last4: Last 4 digits of Aadhaar as a string (e.g. "4321"). Optional.
        pincode:       6-digit pincode as a string (e.g. "400001"). Optional.

    Returns:
        A structured plain-text result the agent reads to form its next response.
        On failure, the message includes what values were checked so the LLM
        can echo them back to the user for confirmation/correction.
    """
    account_data = agent.session_state.get("account_data")
    if not account_data:
        return (
            "ERROR: No account data in session. "
            "The account must be looked up before identity can be verified."
        )

    if not any([dob, aadhaar_last4, pincode]):
        return (
            "VERIFY_INCOMPLETE: No secondary factor provided alongside the name. "
            "Ask the user for their date of birth, Aadhaar last 4 digits, or pincode."
        )

    # ── Increment attempt counter ──────────────────────────────────────────────
    attempts = agent.session_state.get("verification_attempts", 0) + 1
    agent.session_state["verification_attempts"] = attempts
    remaining = VERIFICATION_MAX_ATTEMPTS - attempts

    stored_name: str = account_data.get("full_name", "")

    # ── Step 1: Exact name match ───────────────────────────────────────────────
    name_matched = (stored_name == name.strip())

    # ── Step 2: Secondary factor check (first match wins) ─────────────────────
    factor_matched = False
    factor_label = ""
    factor_value_shown = ""  # what the user gave — echoed back on failure, never the stored value

    if dob is not None:
        # Validate the date format first (catches impossible dates like 1989-02-29)
        if not validate_date(dob.strip()):
            return (
                f"VERIFY_INPUT_ERROR: The date '{dob}' is not a valid calendar date. "
                f"Ask the user to re-enter their date of birth in YYYY-MM-DD format."
            )
        factor_label = "date of birth"
        factor_value_shown = _to_display_date(dob.strip())   # show as DD-MM-YYYY to user
        if account_data.get("dob") == dob.strip():
            factor_matched = True

    elif aadhaar_last4 is not None:
        factor_label = "Aadhaar last 4"
        factor_value_shown = str(aadhaar_last4).strip()
        if account_data.get("aadhaar_last4") == factor_value_shown:
            factor_matched = True

    elif pincode is not None:
        factor_label = "pincode"
        factor_value_shown = str(pincode).strip()
        if account_data.get("pincode") == factor_value_shown:
            factor_matched = True

    # ── Outcome ───────────────────────────────────────────────────────────────
    if name_matched and factor_matched:
        agent.session_state["verified"] = True
        agent.session_state["stage"] = "balance"
        balance = account_data["balance"]
        return (
            f"VERIFY_SUCCESS: Identity verified. "
            f"Outstanding balance: ₹{balance:.2f}. "
            "Inform the user their identity is verified, share their balance, "
            "and ask how much they'd like to pay today."
        )

    # ── Failure path ──────────────────────────────────────────────────────────
    if remaining <= 0:
        agent.session_state["stage"] = "terminated"
        return (
            f"VERIFY_FAILED_TERMINAL: Verification failed. "
            f"All {VERIFICATION_MAX_ATTEMPTS} attempts have been used. "
            "Tell the user their identity could not be verified and the session has been "
            "closed for security. Advise them to contact support."
        )

    # Build a specific failure message so the LLM can echo what it understood
    if not name_matched:
        return (
            f"VERIFY_FAILED: The name '{name}' did not match our records. "
            f"{remaining} attempt(s) remaining. "
            "Tell the user the name you have on file does not match what they provided, "
            "and ask them to confirm their full name exactly as registered."
        )

    # Name matched, secondary factor didn't
    return (
        f"VERIFY_FAILED: Name matched, but the {factor_label} '{factor_value_shown}' "
        f"did not match our records. "
        f"{remaining} attempt(s) remaining. "
        f"Tell the user: 'I checked your {factor_label} as {factor_value_shown} — "
        f"is that correct? If not, please correct it or try a different factor "
        f"(date of birth as DD-MM-YYYY, Aadhaar last 4 digits, or pincode).'"
    )


# ── Helper ────────────────────────────────────────────────────────────────────

def _to_display_date(iso_date: str) -> str:
    """Convert YYYY-MM-DD → DD-MM-YYYY for user-facing display."""
    try:
        y, m, d = iso_date.split("-")
        return f"{d}-{m}-{y}"
    except Exception:
        return iso_date
