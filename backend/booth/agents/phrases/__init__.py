"""Phrasebooks for the template commentary: one module per language, all with the same keys and placeholders.

English is the reference. Numbers are always written with Western digits so the fact-checker can trace them.
"""

from __future__ import annotations

from importlib import import_module

LANGS = ("en", "tr", "es", "de", "fr", "pt", "it", "nl", "ar", "ja", "hi", "sw")

PHRASES: dict[str, dict] = {lang: import_module(f"{__name__}.{lang}").PHRASES for lang in LANGS}


def phrases(lang: str) -> dict:
    """The phrasebook for a language, English when the language has none."""
    return PHRASES.get(lang, PHRASES["en"])


def plural(count: str | int) -> str:
    """English plural suffix; the other phrasebooks ignore the {s_*} placeholders."""
    return "" if str(count) == "1" else "s"
