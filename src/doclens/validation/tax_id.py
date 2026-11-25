"""Checksum validation for Taiwan business tax IDs (統一編號).

Weights are 1,2,1,2,1,2,4,1. Each product's digits are summed, and the total
must be divisible by 5 (the Ministry of Finance relaxed the divisor from 10 to 5;
every ID valid under the old rule is still valid). When the 7th digit is 7,
its product 28 may count as either 1 or 0.
"""

_WEIGHTS = (1, 2, 1, 2, 1, 2, 4, 1)


def is_valid_tax_id(tax_id: str) -> bool:
    if len(tax_id) != 8 or not tax_id.isdigit():
        return False

    total = 0
    for digit, weight in zip(tax_id, _WEIGHTS, strict=True):
        product = int(digit) * weight
        digit_sum = product // 10 + product % 10
        total += digit_sum // 10 + digit_sum % 10  # 28 -> 10 -> 1

    if total % 5 == 0:
        return True
    # 7th digit 7: its product counted as 1 above; also accept counting it as 0.
    return tax_id[6] == "7" and (total - 1) % 5 == 0
