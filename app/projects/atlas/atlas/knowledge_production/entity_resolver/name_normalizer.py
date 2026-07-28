import re
import unicodedata


_COMPANY_SUFFIXES = ("股份有限公司", "有限责任公司", "有限公司", "集团")


def normalize_entity_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    normalized = re.sub(r"[\s·•・\-_.,，。()（）]+", "", normalized)
    for suffix in _COMPANY_SUFFIXES:
        if normalized.endswith(suffix) and len(normalized) > len(suffix):
            normalized = normalized[: -len(suffix)]
            break
    return normalized
