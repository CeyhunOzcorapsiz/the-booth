"""Deterministic commentary used when no model is configured, and as the fallback when one fails.

Templates exist for all twelve broadcast languages (see booth/agents/phrases). Every number they print comes
from the event, the frozen state or the fact sheet, so they always pass the fact-checker.
"""

from __future__ import annotations

import zlib

from booth.agents.phrases import LANGS, phrases, plural
from booth.facts import FactSheet
from booth.sim.match import PITCH_LENGTH, Match, MatchEvent
from booth.sim.tracking import tracking_for

SUPPORTED = LANGS


def _pick(options: list[str], key: str) -> str:
    return options[zlib.crc32(key.encode()) % len(options)]


def _lang(lang: str) -> str:
    return lang if lang in SUPPORTED else "en"


def _names(match: Match, event: MatchEvent) -> dict:
    player = match.player(event.player)
    target = match.player(event.target)
    team = match.teams[event.team].name if event.team else ""
    opp = match.teams["away" if event.team == "home" else "home"].name if event.team else ""
    return {
        "p": player.short_name if player else "",
        "pn": player.number if player else "",
        "t": target.short_name if target else "",
        "team": team,
        "opp": opp,
        "min": event.display_minute,
    }


def story_text(story: dict, lang: str) -> str:
    """A storyline's sentence in ``lang`` (storylines carry every language in ``texts``)."""
    return story.get("texts", {}).get(lang) or story.get(lang) or story["en"]


def describe_location(x: float, y: float, attacking: str | None, lang: str) -> str:
    """Plain-language pitch location relative to the attacking side (used by the accessibility guide)."""
    book = phrases(_lang(lang))
    a = x if attacking != "away" else PITCH_LENGTH - x
    left = y < 22.7 if attacking != "away" else y > 45.3
    right = y > 45.3 if attacking != "away" else y < 22.7
    in_box = a > PITCH_LENGTH - 16.5 and 13.84 < y < 54.16
    zone = (
        "box"
        if in_box
        else "final_third"
        if a > 70
        else "opp_half"
        if a > 52.5
        else "own_half"
        if a > 25
        else "deep"
    )
    side = "left" if left else "right" if right else "middle"
    return book["location"].format(zone=book["zones"][zone], side=book["sides"][side])


def play_by_play(
    event: MatchEvent, match: Match, score: dict, lang: str, style: str, club: str | None = None
) -> str:
    lang = _lang(lang)
    book = phrases(lang)
    table, extras = book["pbp"], book["extras"]
    key = event.type
    if event.type == "shot":
        key = f"shot_{event.outcome}" if f"shot_{event.outcome}" in table else "shot_saved"
    if event.type == "goal" and style == "calm":
        key = "goal_calm"
    if event.type == "pass" and event.outcome == "intercepted":
        key = "pass_intercepted"
    if key not in table:
        return ""
    values = _names(match, event)
    values["score"] = f"{match.teams['home'].name} {score['home']}-{score['away']} {match.teams['away'].name}"
    values["extra"] = event.detail.get("minutes", "")
    text = _pick(table[key], event.id).format(**values)
    if style == "tactical" and event.type in ("goal", "shot", "pass", "foul", "tackle", "interception"):
        text += " " + _tactical_suffix(event, match, lang)
    run = round(tracking_for(match).speed_at(event.player, event.period, event.clock)) if event.player else 0
    if event.type in ("tackle", "interception") and run >= 30 and style in ("hype", "tactical"):
        text += extras["recovery_sprint"].format(run=run)
    speed = event.detail.get("ball_speed_kmh", 0)
    if style in ("hype", "calm", "beginner") and event.type == "shot" and speed >= 100:
        text += extras["fast_shot"].format(speed=speed)
    if style == "hype" and event.type == "pass" and event.detail.get("difficulty", 0) >= 80:
        text += extras["killer_pass"]
    if style == "hype" and event.type in ("goal", "red_card", "penalty_awarded"):
        text = text.rstrip(".!。！।") + ("！！" if lang == "ja" else "!!")
    if club and event.type in ("goal", "penalty_awarded", "red_card") and event.team:
        ours = event.team == club if event.type != "red_card" else event.team != club
        name = match.teams[club].name
        text = (extras["club_yes"] if ours else extras["club_bad"].format(name=name)) + text
    return f"{event.display_minute} {text}"


def _tactical_suffix(event: MatchEvent, match: Match, lang: str) -> str:
    extras = phrases(lang)["extras"]
    where = describe_location(event.x, event.y, event.team, lang)
    if event.type == "shot" and "distance_m" in event.detail:
        speed = event.detail.get("ball_speed_kmh")
        kmh = f", {speed} {extras['kmh']}" if speed else ""
        return f"({event.detail['distance_m']} m{kmh}, {where})"
    if event.type == "pass" and "pass_distance_m" in event.detail:
        label = extras["difficulty"]
        return f"({event.detail['pass_distance_m']} m, {label} {event.detail['difficulty']}/100, {where})"
    if event.type == "goal":
        assist = match.player(event.target)
        if assist:
            return f"({extras['assist']}: {assist.short_name}, {where})"
    return f"({where})"


def explain(event_type: str, lang: str) -> str | None:
    return phrases(_lang(lang))["explain"].get(event_type)


def spatial(event: MatchEvent, match: Match, lang: str) -> str:
    lang = _lang(lang)
    team = event.possession
    if team is None:
        return ""
    name = match.teams[team].name
    x, y = (event.end_x, event.end_y) if event.end_x is not None else (event.x, event.y)
    where = describe_location(x, y, team, lang)
    return phrases(lang)["spatial"].format(team=name, where=where)


def _mood(momentum: str, match: Match, lang: str) -> str:
    """The momentum fact ("<team> on top" / "evenly balanced") in ``lang``."""
    color = phrases(lang)["color"]
    for team in match.teams.values():
        if momentum == f"{team.name} on top":
            return color["on_top"].format(team=team.name)
    return color["balanced"]


def color(event: MatchEvent, match: Match, sheet: FactSheet, lang: str, storylines: list[dict] = ()) -> str:
    """One or two sentences of analysis built only from facts on the sheet, shaped by the kind of moment."""
    lang = _lang(lang)
    book = phrases(lang)["color"]
    facts = sheet.facts
    team = event.team or "home"
    name = match.teams[team].name
    player = match.player(event.player)

    def val(fact_id: str) -> str | None:
        fact = facts.get(fact_id)
        return fact.value if fact else None

    shots, on_target = val(f"F-{team}-shots"), val(f"F-{team}-shots_on_target")
    poss, momentum = val(f"F-{team}-possession_pct"), val("F-momentum")
    stories = sorted((st for st in storylines if st["event_id"] == event.id), key=_story_rank)
    parts: list[str] = [story_text(st, lang) for st in stories[:2]]
    has_tally = any(st["kind"] in ("brace", "hat_trick", "haul") for st in stories)
    if parts and event.type == "goal":
        pass  # the storyline already says what matters about this goal
    elif event.type == "goal" and player and not has_tally:
        goals = val(f"F-{event.player}-goals")
        if goals and int(goals) > 1:
            parts.append(book["goal_tally"].format(goals=goals, player=player.short_name))
        if shots and on_target:
            parts.append(
                book["team_shots"].format(team=name, shots=shots, on=on_target, s_shots=plural(shots))
            )
    elif event.type in ("yellow_card", "red_card") and player:
        fouls = val(f"F-{event.player}-fouls")
        if fouls:
            parts.append(
                book["player_fouls"].format(player=player.short_name, fouls=fouls, s_fouls=plural(fouls))
            )
        cards = val(f"F-{team}-yellow_cards")
        if cards:
            parts.append(book["team_cards"].format(team=name, cards=cards, s_cards=plural(cards)))
    elif event.type == "shot" and on_target:
        parts.append(book["on_target"].format(team=name, on=on_target, s_on=plural(on_target)))
    if momentum and len(parts) < 2 and not stories:
        parts.append(book["momentum"].format(mood=_mood(momentum, match, lang)))
    if poss and len(parts) < 2 and not stories:
        parts.append(book["possession"].format(team=name, poss=poss))
    return " ".join(parts[:2])


def stat_caption(sheet: FactSheet, lang: str) -> str:
    """Head-to-head line such as "Possession 54-46 · Shots 7-5"; falls back to listing facts."""
    book = phrases(_lang(lang))["stats"]
    pairs = []
    for stat in ("possession_pct", "shots", "shots_on_target", "corners"):
        home, away = sheet.facts.get(f"F-home-{stat}"), sheet.facts.get(f"F-away-{stat}")
        if home and away:
            pairs.append(f"{book[stat]} {home.value}-{away.value}")
    if not pairs:
        pairs = [f"{f.label}: {f.value}" for f in list(sheet.facts.values())[:4]]
    return book["prefix"] + " · ".join(pairs)


STORY_PRIORITY = (
    "comeback",
    "late_winner",
    "late_equalizer",
    "turnaround",
    "hat_trick",
    "down_to_ten",
    "quick_fire",
    "brace",
    "against_the_run",
    "control",
    "chaos",
    "haul",
)


def _story_rank(story: dict) -> int:
    return STORY_PRIORITY.index(story["kind"]) if story["kind"] in STORY_PRIORITY else len(STORY_PRIORITY)


def _top_runner(match: Match, sheet: FactSheet | None) -> tuple[str, str] | None:
    """(name, km) of the biggest runner on the sheet, if the stats producer fetched running stats."""
    if sheet is None:
        return None
    best = None
    for fact_id, fact in sheet.facts.items():
        parts = fact_id.split("-")
        if len(parts) == 3 and parts[2] == "distance_km" and parts[1][:1] in ("H", "A"):
            player = match.player(parts[1])
            if player and (best is None or float(fact.value) > float(best[1])):
                best = (player.short_name, fact.value)
    return best


def recap(match: Match, snapshot: dict, lang: str, final: bool, sheet: FactSheet | None = None) -> str:
    lang = _lang(lang)
    book = phrases(lang)["recap"]
    runner = _top_runner(match, sheet)
    stories = sorted(snapshot.get("storylines", []), key=_story_rank)
    story = (" " + story_text(stories[0], lang)) if stories else ""
    home, away = match.teams["home"].name, match.teams["away"].name
    s = snapshot["score"]
    th, ta = snapshot["teams"]["home"], snapshot["teams"]["away"]
    goals = [m for m in snapshot["key_moments"] if m["type"] == "goal"]
    head = book["full"] if final else book["half"]
    scorers = ", ".join(f"{m['player']} {m['minute']}" for m in goals) or book["no_goals"]
    body = book["body"].format(
        ph=th["possession_pct"],
        pa=ta["possession_pct"],
        sh=th["shots"],
        sa=ta["shots"],
        oh=th["shots_on_target"],
        oa=ta["shots_on_target"],
    )
    return (
        book["headline"].format(head=head, match=f"{home} {s['home']}-{s['away']} {away}")
        + f"{story} {book['goals'].format(scorers=scorers)} {body}"
        + (book["runner"].format(name=runner[0], km=runner[1]) if runner else "")
    )
