"""Card number, CVV, and expiry validators."""
from datetime import date


def normalize_card_number(raw: str) -> str:
    """Strip spaces, dashes, and non-digits: '4532 0151 1283 0366' → '4532015112830366'."""
    return "".join(c for c in raw if c.isdigit())


def is_amex(card_number: str) -> bool:
    """American Express cards start with 34 or 37."""
    digits = normalize_card_number(card_number)
    return digits.startswith(("34", "37"))


def luhn_check(card_number: str) -> bool:
    """Validate card number using the Luhn algorithm."""
    digits = [int(d) for d in normalize_card_number(card_number)]
    if len(digits) < 13 or len(digits) > 19:
        return False
    total = 0
    for i, digit in enumerate(reversed(digits)):
        if i % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def validate_card_length(card_number: str) -> bool:
    digits = normalize_card_number(card_number)
    return 13 <= len(digits) <= 19


def validate_cvv(cvv: str, card_number: str) -> bool:
    """4 digits for Amex, 3 for all others."""
    if not cvv.isdigit():
        return False
    expected = 4 if is_amex(card_number) else 3
    return len(cvv) == expected


def validate_expiry(month: int, year: int) -> bool:
    """Card is valid if expiry month/year >= current month/year."""
    try:
        if not (1 <= month <= 12):
            return False
        today = date.today()
        return (year, month) >= (today.year, today.month)
    except (ValueError, OverflowError):
        return False
