"""Convert numeric amounts into Indian-English words for invoice printing.

Uses the Indian numbering system (units, tens, hundreds, thousand, lakh, crore)
rather than the international system (thousand, million, billion). Supports
values from 0 up to 99,99,99,999.99 (99 crore range) with two-decimal paise.
"""
from decimal import ROUND_HALF_UP, Decimal

_ONES = [
    "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
    "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
    "Seventeen", "Eighteen", "Nineteen",
]
_TENS = [
    "", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety",
]

MAX_SUPPORTED = 999_999_99_999  # 99,99,99,999 as per spec ceiling


def _two_digits_to_words(number: int) -> str:
    if number == 0:
        return ""
    if number < 20:
        return _ONES[number]
    tens, ones = divmod(number, 10)
    return f"{_TENS[tens]} {_ONES[ones]}".strip()


def _three_digits_to_words(number: int) -> str:
    if number == 0:
        return ""
    hundreds, remainder = divmod(number, 100)
    parts = []
    if hundreds:
        parts.append(f"{_ONES[hundreds]} Hundred")
    if remainder:
        parts.append(_two_digits_to_words(remainder))
    return " ".join(parts)


def _integer_to_indian_words(number: int) -> str:
    """Convert a non-negative integer to words using Indian place-value groups."""
    if number == 0:
        return "Zero"

    if number > MAX_SUPPORTED:
        raise ValueError(f"Number {number} exceeds supported range of {MAX_SUPPORTED}")

    crore, remainder = divmod(number, 1_00_00_000)
    lakh, remainder = divmod(remainder, 1_00_000)
    thousand, remainder = divmod(remainder, 1_000)
    hundred_part = remainder

    segments = []
    if crore:
        segments.append(f"{_integer_to_indian_words(crore)} Crore")
    if lakh:
        segments.append(f"{_two_digits_to_words(lakh)} Lakh")
    if thousand:
        segments.append(f"{_two_digits_to_words(thousand)} Thousand")
    if hundred_part:
        segments.append(_three_digits_to_words(hundred_part))

    return " ".join(segment for segment in segments if segment).strip()


def number_to_indian_words(amount: float | int | Decimal) -> str:
    """Render a rupee amount as words, e.g. 150000 -> 'One Lakh Fifty Thousand Rupees Only'.

    Paise (decimal remainder) are appended as '<Words> Paise' when present.
    """
    decimal_amount = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if decimal_amount < 0:
        raise ValueError("Amount must be non-negative")

    rupees = int(decimal_amount)
    paise = int((decimal_amount - rupees) * 100)

    rupee_words = _integer_to_indian_words(rupees)

    if paise:
        paise_words = _two_digits_to_words(paise)
        return f"{rupee_words} Rupees and {paise_words} Paise Only"
    return f"{rupee_words} Rupees Only"
