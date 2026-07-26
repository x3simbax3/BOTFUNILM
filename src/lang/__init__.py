"""Localized presentation strings.

Add a sibling package with the same public API as ``ru`` and register its code
in ``SUPPORTED_LOCALES`` to introduce another translation.
"""

from functools import lru_cache
from importlib import import_module
from types import ModuleType

DEFAULT_LOCALE = "ru"
SUPPORTED_LOCALES = frozenset({DEFAULT_LOCALE})


def normalize_locale(language_code: str | None) -> str:
    if not language_code:
        return DEFAULT_LOCALE
    locale = language_code.lower().replace("-", "_").split("_", 1)[0]
    return locale if locale in SUPPORTED_LOCALES else DEFAULT_LOCALE


@lru_cache
def get_locale(language_code: str | None = None) -> ModuleType:
    return import_module(f"{__name__}.{normalize_locale(language_code)}")


from .ru import *  # noqa: E402,F403
from .ru import __all__ as _ru_all

__all__ = (
    "DEFAULT_LOCALE",
    "SUPPORTED_LOCALES",
    "get_locale",
    "normalize_locale",
    *_ru_all,
)
