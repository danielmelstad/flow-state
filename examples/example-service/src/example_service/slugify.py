"""URL slug generation."""

import re
import unicodedata

_INVALID = re.compile(r"[^a-z0-9]+")


def slugify(text: str, max_length: int = 64) -> str:
    """Return a URL-safe slug for *text*.

    Lowercases, strips accents, collapses any run of non-alphanumeric
    characters into a single hyphen, and truncates to *max_length* without
    leaving a trailing hyphen.
    """
    if max_length < 1:
        raise ValueError("max_length must be >= 1")
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    slug = _INVALID.sub("-", normalized.lower()).strip("-")
    return slug[:max_length].rstrip("-")
