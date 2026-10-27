"""Neural voices from Azure AI Speech, proxied by the server so the key never reaches the browser.

Optional: set ``AZURE_SPEECH_KEY`` and ``AZURE_SPEECH_REGION`` (the free F0 tier is enough for demos).
Without them the frontend uses the browser's built-in speech synthesis.
"""

from __future__ import annotations

import logging
import os
from collections import OrderedDict
from xml.sax.saxutils import escape

import httpx

from booth.limits import DailyBudget

log = logging.getLogger("booth.speech")

# One female and one male neural voice per broadcast language.
VOICES = {
    "en": {"female": "en-GB-SoniaNeural", "male": "en-GB-RyanNeural"},
    "tr": {"female": "tr-TR-EmelNeural", "male": "tr-TR-AhmetNeural"},
    "es": {"female": "es-ES-ElviraNeural", "male": "es-ES-AlvaroNeural"},
    "de": {"female": "de-DE-KatjaNeural", "male": "de-DE-ConradNeural"},
    "fr": {"female": "fr-FR-DeniseNeural", "male": "fr-FR-HenriNeural"},
    "pt": {"female": "pt-BR-FranciscaNeural", "male": "pt-BR-AntonioNeural"},
    "it": {"female": "it-IT-ElsaNeural", "male": "it-IT-DiegoNeural"},
    "ar": {"female": "ar-SA-ZariyahNeural", "male": "ar-SA-HamedNeural"},
    "nl": {"female": "nl-NL-ColetteNeural", "male": "nl-NL-MaartenNeural"},
    "ja": {"female": "ja-JP-NanamiNeural", "male": "ja-JP-KeitaNeural"},
    "hi": {"female": "hi-IN-SwaraNeural", "male": "hi-IN-MadhurNeural"},
    "sw": {"female": "sw-KE-ZuriNeural", "male": "sw-KE-RafikiNeural"},
}
GENDERS = ("female", "male")
OUTPUT_FORMAT = "audio-24khz-48kbitrate-mono-mp3"
CACHE_SIZE = 400


class SpeechUnavailable(RuntimeError):
    pass


class Speech:
    def __init__(
        self,
        key: str | None = None,
        region: str | None = None,
        daily_chars: int | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.key = key if key is not None else os.getenv("AZURE_SPEECH_KEY")
        self.region = region if region is not None else os.getenv("AZURE_SPEECH_REGION")
        limit = (
            daily_chars if daily_chars is not None else int(os.getenv("BOOTH_SPEECH_DAILY_CHARS", "15000"))
        )
        self.chars = DailyBudget(limit)
        self._transport = transport
        self._cache: OrderedDict[tuple[str, str, str], bytes] = OrderedDict()

    @property
    def enabled(self) -> bool:
        return bool(self.key and self.region)

    def status(self) -> dict:
        return {
            "enabled": self.enabled,
            "provider": "azure-ai-speech" if self.enabled else "browser",
            **self.chars.status(),
        }

    @staticmethod
    def ssml(text: str, lang: str, gender: str = "female") -> str:
        voice = VOICES.get(lang, VOICES["en"])[gender if gender in GENDERS else "female"]
        locale = "-".join(voice.split("-")[:2])
        return (
            f"<speak version='1.0' xml:lang='{locale}'><voice name='{voice}'>"
            f"<prosody rate='+8%'>{escape(text)}</prosody></voice></speak>"
        )

    async def synthesize(self, text: str, lang: str, gender: str = "female") -> bytes:
        if not self.enabled:
            raise SpeechUnavailable("Azure AI Speech is not configured")
        key = (lang, gender, text)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        if not self.chars.take(len(text)):
            raise SpeechUnavailable("daily speech budget reached")
        url = f"https://{self.region}.tts.speech.microsoft.com/cognitiveservices/v1"
        headers = {
            "Ocp-Apim-Subscription-Key": self.key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": OUTPUT_FORMAT,
            "User-Agent": "the-booth",
        }
        try:
            async with httpx.AsyncClient(timeout=10, transport=self._transport) as client:
                response = await client.post(
                    url, headers=headers, content=self.ssml(text, lang, gender).encode()
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            log.warning("speech synthesis failed: %s", exc)
            raise SpeechUnavailable("speech synthesis failed") from exc
        audio = response.content
        self._cache[key] = audio
        while len(self._cache) > CACHE_SIZE:
            self._cache.popitem(last=False)
        return audio
