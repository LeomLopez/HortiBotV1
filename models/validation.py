import unicodedata


VALID_UNITS = {"kg", "unid"}


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def normalize_unidade(unidade: str | None) -> str:
    raw = str(unidade or "").strip().lower()
    if not raw:
        return ""

    return _strip_accents(raw)


def is_valid_unidade(unidade: str | None) -> bool:
    return normalize_unidade(unidade) in VALID_UNITS


def unidade_error_message() -> str:
    return "Informe uma unidade válida. Use apenas: kg ou unid."
