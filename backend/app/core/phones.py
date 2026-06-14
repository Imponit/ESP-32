"""Нормализация телефонов (единая точка для поиска и дедупликации).

Оставляем только цифры; российские 11-значные номера с ведущей 7/8 приводим к
10 цифрам, чтобы +7 / 8 / разделители не мешали сравнению и поиску.
"""

import re


def normalize_phone(phone: str | None) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 11 and digits[0] in "78":
        digits = digits[1:]
    return digits
