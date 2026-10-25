import asyncio
import string

import pytest

from booth.agents import templates
from booth.agents.phrases import LANGS, PHRASES
from booth.crew import Crew
from booth.orchestrator import Broadcast
from booth.overlays import LABELS
from booth.profile import LANGUAGES, ViewerProfile
from booth.sim.match import generate_match

OPTIONAL = {"s_shots", "s_fouls", "s_cards", "s_on", "s_changes"}  # English plural helpers


def _fields(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def test_every_broadcast_language_has_a_phrasebook():
    assert set(LANGS) == set(LANGUAGES)
    assert set(templates.SUPPORTED) == set(LANGUAGES)
    assert set(LABELS) == set(LANGUAGES)


@pytest.mark.parametrize("lang", [lang for lang in LANGS if lang != "en"])
def test_phrasebook_matches_english_keys_and_placeholders(lang):
    reference = PHRASES["en"]
    book = PHRASES[lang]
    assert set(book) == set(reference), lang
    for section, value in reference.items():
        if isinstance(value, dict):
            assert set(book[section]) == set(value), (lang, section)
            for key, text in value.items():
                options = text if isinstance(text, list) else [text]
                theirs = book[section][key] if isinstance(book[section][key], list) else [book[section][key]]
                expected = set().union(*(_fields(t) for t in options)) - OPTIONAL
                for t in theirs:
                    assert _fields(t) - OPTIONAL <= expected | {"team", "p", "t", "score"}, (
                        lang,
                        section,
                        key,
                        t,
                    )
                    if section == "pbp":
                        continue  # play-by-play variants may drop a name
                    assert expected <= _fields(t), (lang, section, key, t)
        else:
            assert _fields(book[section]) == _fields(value), (lang, section)


def test_template_broadcast_is_verified_in_every_language():
    """A full offline broadcast in each language: everything native and everything fact-checked."""
    match = generate_match(119)
    crew = Crew(None)

    async def run(lang):
        segments = []
        show = Broadcast(match, ViewerProfile(lang, "tactical", club="home"), crew, speed=1e9, max_gap_s=0)
        async for message in show.stream():
            if message["type"] == "segment":
                segments.append(message)
        return segments

    for lang in LANGS:
        segments = asyncio.run(run(lang))
        assert segments, lang
        assert all(s["lang"] == lang for s in segments), lang
        assert all(s["verified"] for s in segments), [s["text"] for s in segments if not s["verified"]][:3]


def test_storylines_carry_every_language():
    from booth.state import MatchState

    state = MatchState(generate_match(119))
    for event in state.match.events:
        state.apply(event)
    stories = state.snapshot()["storylines"]
    assert stories
    for story in stories:
        assert set(story["texts"]) == set(LANGS)
        assert story["en"] == story["texts"]["en"] and story["tr"] == story["texts"]["tr"]
