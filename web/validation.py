import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.utils import timezone


LIMITS = {
    "username": 30,
    "email": 35,
    "password_min": 8,
    "password": 15,
    "event_name": 100,
    "place": 150,
    "description": 500,
    "service_name": 80,
    "service_description": 200,
    "invite_code": 20,
    "people": 1000,
    "money": 9999999,
}

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")
CODE_RE = re.compile(r"^[A-Z0-9]{1,20}$")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
DECIMAL_RE = re.compile(r"^\d{1,7}(\.\d{1,2})?$")


class InputValidationError(ValueError):
    pass


def form_limits(request):
    return {"FORM_LIMITS": LIMITS}


def clean_text(value, field_name, max_length, required=False, min_length=0, pattern=None):
    text = (value or "").strip()

    if required and not text:
        raise InputValidationError(f"{field_name} es obligatorio.")

    if text and len(text) < min_length:
        raise InputValidationError(
            f"{field_name} debe tener al menos {min_length} caracteres."
        )

    if len(text) > max_length:
        raise InputValidationError(
            f"{field_name} no puede superar {max_length} caracteres."
        )

    if pattern and text and not pattern.fullmatch(text):
        raise InputValidationError(f"{field_name} tiene un formato no válido.")

    return text


def clean_username(value):
    return clean_text(
        value,
        "El usuario",
        LIMITS["username"],
        required=True,
        min_length=3,
        pattern=USERNAME_RE,
    )


def clean_email(value):
    email = clean_text(value, "El correo", LIMITS["email"], required=True).lower()

    try:
        validate_email(email)
    except DjangoValidationError as exc:
        raise InputValidationError("Correo no válido.") from exc

    return email


def clean_password(value, field_name="La contraseña"):
    password = (value or "").strip()

    if not password:
        raise InputValidationError(f"{field_name} es obligatoria.")

    if len(password) < LIMITS["password_min"]:
        raise InputValidationError(
            f"{field_name} debe tener al menos {LIMITS['password_min']} caracteres."
        )

    if len(password) > LIMITS["password"]:
        raise InputValidationError(
            f"{field_name} no puede superar {LIMITS['password']} caracteres."
        )

    return password


def clean_optional_password(value):
    password = (value or "").strip()

    if len(password) > LIMITS["password"]:
        raise InputValidationError(
            f"La contraseña no puede superar {LIMITS['password']} caracteres."
        )

    return password


def clean_invite_code(value):
    return clean_text(
        value,
        "El código",
        LIMITS["invite_code"],
        required=True,
        pattern=CODE_RE,
    ).upper()


def clean_int(value, field_name, min_value=1, max_value=LIMITS["people"]):
    raw = (value or "").strip()

    if not raw:
        raise InputValidationError(f"{field_name} es obligatorio.")

    if len(raw) > len(str(max_value)):
        raise InputValidationError(f"{field_name} no puede superar {max_value}.")

    if not raw.isdigit():
        raise InputValidationError(f"{field_name} debe contener solo números.")

    number = int(raw)

    if number < min_value:
        raise InputValidationError(f"{field_name} debe ser mayor o igual a {min_value}.")

    if number > max_value:
        raise InputValidationError(f"{field_name} no puede superar {max_value}.")

    return number


def clean_decimal(value, field_name="El precio", default="0.00"):
    raw = (value if value not in (None, "") else default)
    raw = str(raw).strip()

    if len(raw) > 10 or not DECIMAL_RE.fullmatch(raw):
        raise InputValidationError(
            f"{field_name} debe ser un número válido de hasta 7 dígitos y 2 decimales."
        )

    try:
        amount = Decimal(raw).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError) as exc:
        raise InputValidationError(f"{field_name} no es válido.") from exc

    if amount < 0:
        raise InputValidationError(f"{field_name} no puede ser negativo.")

    if amount > Decimal(str(LIMITS["money"])):
        raise InputValidationError(f"{field_name} no puede superar {LIMITS['money']}.")

    return amount


def clean_future_date(value, field_name="La fecha"):
    raw = clean_text(value, field_name, 10, required=True)

    try:
        date_value = datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError as exc:
        raise InputValidationError(f"{field_name} no es válida.") from exc

    if date_value < timezone.localdate():
        raise InputValidationError("No puedes poner una fecha anterior a la actual.")

    return date_value


def clean_time(value, field_name="La hora"):
    raw = clean_text(value, field_name, 5, required=True)

    if not TIME_RE.fullmatch(raw):
        raise InputValidationError(f"{field_name} no es válida.")

    return raw


def clean_id_list(values, field_name, max_items=20):
    cleaned = []

    for raw in values[:max_items]:
        text = str(raw).strip()

        if len(text) > 10 or not text.isdigit():
            raise InputValidationError(f"{field_name} contiene una opción no válida.")

        cleaned.append(text)

    return cleaned
