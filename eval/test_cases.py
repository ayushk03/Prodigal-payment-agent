"""
Test cases for the Payment Collection Agent.

Each test case is a dict with:
  name        : identifier
  description : what this tests
  turns       : list of (user_input, assertions_dict) tuples
  expect_stage: final session stage expected after the last turn
"""
from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# Assertion helpers (checked in evaluator.py)
# ─────────────────────────────────────────────────────────────────────────────
# Each assertion is a callable: fn(message: str) -> bool
def contains(keyword: str):
    return lambda msg: keyword.lower() in msg.lower()

def not_contains(keyword: str):
    return lambda msg: keyword.lower() not in msg.lower()

def any_of(*keywords):
    return lambda msg: any(k.lower() in msg.lower() for k in keywords)


# ─────────────────────────────────────────────────────────────────────────────
# Test Definitions
# ─────────────────────────────────────────────────────────────────────────────

TEST_CASES: list[dict[str, Any]] = [

    # 1. Happy path (DOB, full payment)
    {
        "name": "happy_path_dob",
        "description": "Full successful flow — ACC1001, verify via DOB",
        "turns": [
            ("Hi",                          [contains("account")]),
            ("My account is ACC1001",        [any_of("name", "verify")]),
            ("Nithin Jain",                  [any_of("dob", "date", "aadhaar", "pincode", "verify")]),
            ("DOB is 1990-05-14",            [any_of("balance", "1250", "1,250"), not_contains("1990-05-14")]),
            ("I want to pay the full amount",[any_of("card", "number", "cvv")]),
            ("Card number 4532015112830366", [any_of("cvv", "expiry", "cardholder")]),
            ("CVV 123 expires 12/2027",      [any_of("name", "cardholder", "processed", "transaction")]),
            ("Nithin Jain",                  [any_of("success", "processed", "transaction")]),
        ],
        "expect_stage": "done",
        "expect_transaction_id": True,
    },

    # 2. Happy path (Aadhaar, partial payment)
    {
        "name": "happy_path_aadhaar_partial",
        "description": "Verify via Aadhaar last 4, partial payment of ₹500",
        "turns": [
            ("hello",                       [contains("account")]),
            ("acc1001",                     [any_of("name", "verify")]),
            ("name is Nithin Jain",         [any_of("dob", "aadhaar", "pincode")]),
            ("aadhaar last 4 is 4321",      [contains("balance"), not_contains("4321")]),
            ("pay 500",                     [any_of("card", "number", "details")]),
            ("4532015112830366 cvv 123 expires december 2027 cardholder Nithin Jain",
                                            [any_of("success", "transaction", "processed")]),
        ],
        "expect_stage": "done",
        "expect_transaction_id": True,
    },

    # 3. Account not found
    {
        "name": "account_not_found",
        "description": "Non-existent account ID",
        "turns": [
            ("hi",                          [contains("account")]),
            ("ACC9999",                     [any_of("not found", "check", "re-enter")]),
        ],
        "expect_stage": "greeting",
        "expect_transaction_id": False,
    },

    # 4. Verification fails completely (terminates)
    {
        "name": "verification_wrong_name_exhausted",
        "description": "Wrong name 3 times → session terminated",
        "turns": [
            ("hi",                          [contains("account")]),
            ("ACC1001",                     [any_of("name", "verify")]),
            ("John Smith dob 1990-05-14",   [any_of("match", "try", "attempt", "incorrect")]),
            ("John Smith dob 1990-05-14",   [any_of("match", "try", "attempt", "incorrect")]),
            ("John Smith dob 1990-05-14",   [any_of("closed", "terminated", "support", "security", "failed")]),
        ],
        "expect_stage": "terminated",
        "expect_transaction_id": False,
    },

    # 5. Verification succeeds on retry
    {
        "name": "verification_succeeds_on_retry",
        "description": "Wrong secondary factor once, correct on retry",
        "turns": [
            ("hi",                          [contains("account")]),
            ("ACC1001",                     [any_of("name", "verify")]),
            ("Nithin Jain",                 [any_of("dob", "aadhaar", "pincode")]),
            ("dob 2000-01-01",              [any_of("match", "try", "attempt", "incorrect")]),
            ("dob 1990-05-14",              [contains("balance")]),
        ],
        "expect_stage": "balance",
        "expect_transaction_id": False,
    },

    # 6. Payment validation failure (Luhn check)
    {
        "name": "payment_invalid_card_luhn",
        "description": "Card fails Luhn check — pre-validation catches it",
        "turns": [
            ("hi",                          [contains("account")]),
            ("ACC1001",                     [any_of("name", "verify")]),
            ("Nithin Jain",                 [any_of("dob", "aadhaar", "pincode")]),
            ("1990-05-14",                  [contains("balance")]),
            ("pay 500",                     [any_of("card", "number", "details")]),
            ("card 1234567890123456 cvv 123 expiry 12 2027 name Nithin Jain",
                                            [any_of("invalid", "check", "luhn", "failed")]),
        ],
        "expect_stage": "balance",   
        "expect_transaction_id": False,
    },

    # 7. Payment API failure (Insufficient balance)
    {
        "name": "payment_insufficient_balance",
        "description": "Amount exceeds balance",
        "turns": [
            ("hi",                          [contains("account")]),
            ("ACC1001",                     [any_of("name", "verify")]),
            ("Nithin Jain",                 [any_of("dob", "aadhaar", "pincode")]),
            ("1990-05-14",                  [contains("balance")]),
            ("I want to pay 5000 rupees",   [any_of("balance", "exceed", "lower", "amount", "failed")]),
        ],
        "expect_stage": "balance",
        "expect_transaction_id": False,
    },

    # 8. Zero balance edge case
    {
        "name": "zero_balance_account",
        "description": "ACC1003 has ₹0 balance — agent should surface this",
        "turns": [
            ("hi",                          [contains("account")]),
            ("ACC1003",                     [any_of("name", "verify")]),
            ("Priya Agarwal",               [any_of("dob", "aadhaar", "pincode")]),
            ("1992-08-10",                  [any_of("0", "zero", "balance")]),
        ],
        "expect_stage": "balance",
        "expect_transaction_id": False,
    },

    # 9. Leap year date edge case
    {
        "name": "leap_year_dob_valid",
        "description": "ACC1004 — DOB 1988-02-29 is a real leap year",
        "turns": [
            ("hi",                          [contains("account")]),
            ("ACC1004",                     [any_of("name", "verify")]),
            ("Rahul Mehta",                 [any_of("dob", "aadhaar", "pincode")]),
            ("dob 1988-02-29",              [contains("balance")]),
        ],
        "expect_stage": "balance",
        "expect_transaction_id": False,
    },

    # 10. Messy NLP handling
    {
        "name": "messy_nlp_parsing",
        "description": "Out of order name, natural language dates, spacing in card",
        "turns": [
            ("hi, I'm Nithin Jain and my account is ACC1001",
                                            [any_of("dob", "aadhaar", "pincode", "verify", "date")]),
            ("DOB 14 May 1990",             [contains("balance")]),
            ("full amount",                 [any_of("card", "number")]),
            ("the card number is 4532 0151 1283 0366", [any_of("cvv", "expiry")]),
            ("cvv 123 expiry december 2027 name Nithin Jain",
                                            [any_of("success", "transaction", "processed")]),
        ],
        "expect_stage": "done",
        "expect_transaction_id": True,
    },
]
