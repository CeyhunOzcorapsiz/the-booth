"""What a single viewer wants from their broadcast."""

from __future__ import annotations

from dataclasses import asdict, dataclass

STYLES = ("hype", "calm", "tactical", "beginner")
LANGUAGES = {
    "en": "English",
    "tr": "Turkish",
    "es": "Spanish",
    "de": "German",
    "fr": "French",
    "pt": "Portuguese",
    "it": "Italian",
    "ar": "Arabic",
    "nl": "Dutch",
    "ja": "Japanese",
    "hi": "Hindi",
    "sw": "Swahili",
}


@dataclass(frozen=True)
class ViewerProfile:
    lang: str = "en"
    style: str = "hype"
    accessible: bool = False
    follow: str | None = None

    def __post_init__(self):
        if self.lang not in LANGUAGES:
            raise ValueError(f"Unsupported language '{self.lang}'.")
        if self.style not in STYLES:
            raise ValueError(f"Unknown style '{self.style}'.")
        if self.follow is not None and (len(self.follow) > 4 or self.follow[:1] not in ("H", "A")):
            raise ValueError("follow must be a player id such as H9 or A10.")

    @property
    def language_name(self) -> str:
        return LANGUAGES[self.lang]

    def key(self) -> str:
        return f"{self.lang}|{self.style}|{int(self.accessible)}|{self.follow or '-'}"

    def to_dict(self) -> dict:
        return asdict(self)
