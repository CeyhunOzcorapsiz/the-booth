"""Deterministic commentary used when no model is configured, and as the fallback when one fails.

Templates exist for English and Turkish. Every number they print comes from the event, the frozen state or
the fact sheet, so they always pass the fact-checker.
"""

from __future__ import annotations

import zlib

from booth.facts import FactSheet
from booth.sim.match import PITCH_LENGTH, Match, MatchEvent

SUPPORTED = ("en", "tr")


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


def describe_location(x: float, y: float, attacking: str | None, lang: str) -> str:
    """Plain-language pitch location relative to the attacking side (used by the accessibility guide)."""
    lang = _lang(lang)
    a = x if attacking != "away" else PITCH_LENGTH - x
    left = y < 22.7 if attacking != "away" else y > 45.3
    right = y > 45.3 if attacking != "away" else y < 22.7
    in_box = a > PITCH_LENGTH - 16.5 and 13.84 < y < 54.16
    if lang == "tr":
        zone = (
            "ceza sahasının içinde"
            if in_box
            else "son üçte birlik bölgede"
            if a > 70
            else "rakip yarı alanda"
            if a > 52.5
            else "kendi yarı alanında"
            if a > 25
            else "kendi kalesinin önünde"
        )
        side = "sol tarafta" if left else "sağ tarafta" if right else "ortada"
        return f"{zone}, {side}"
    zone = (
        "inside the box"
        if in_box
        else "in the final third"
        if a > 70
        else "in the opposition half"
        if a > 52.5
        else "in their own half"
        if a > 25
        else "deep in their own half"
    )
    side = "on the left" if left else "on the right" if right else "through the middle"
    return f"{zone}, {side}"


PBP = {
    "en": {
        "kickoff": ["{team} get us under way.", "And we're off, {team} kick off."],
        "goal": ["GOAL! {p} scores for {team}! {score}.", "It's in! {p} finds the net for {team}. {score}."],
        "goal_calm": ["Goal for {team}, scored by {p}. {score}."],
        "shot_saved": ["{p} shoots, saved by the keeper.", "Effort from {p}, a comfortable stop."],
        "shot_off_target": ["{p} goes for goal but it's wide.", "{p} pulls the trigger, off target."],
        "shot_blocked": ["{p}'s shot is blocked.", "{p} lets fly, charged down."],
        "corner": ["Corner to {team}, {p} to take it.", "{team} win a corner."],
        "foul": ["Free kick: {p} brings down {t}.", "Foul by {p} on {t}."],
        "yellow_card": ["Yellow card for {p} of {team}.", "{p} goes into the book."],
        "red_card": [
            "Red card! {p} is sent off, {team} down to ten.",
            "{p} sees red and {team} are a man down.",
        ],
        "penalty_awarded": [
            "Penalty to {team}! {t} brings down {p}.",
            "The referee points to the spot for {team}!",
        ],
        "free_kick": ["{p} stands over a free kick in a dangerous area."],
        "offside": ["Flag goes up, {p} is offside."],
        "substitution": ["Change for {team}: {p} on, {t} off."],
        "stoppage_time": ["We'll play {extra} added minutes."],
        "half_time": ["Half time. {score}."],
        "full_time": ["Full time! It finishes {score}."],
        "pass": ["{p} plays it to {t}.", "{p} finds {t}."],
        "pass_intercepted": ["{p}'s pass is cut out.", "{p} tries to play it forward, intercepted."],
        "tackle": ["Strong tackle from {p} on {t}."],
        "interception": ["{p} reads it and intercepts."],
    },
    "tr": {
        "kickoff": ["Santrayı {team} yapıyor, maç başladı.", "Ve başlıyoruz, top {team} ekibinde."],
        "goal": ["GOOOL! {p}, {team} için ağları sarsıyor! {score}.", "Top ağlarda! {p} attı, {score}."],
        "goal_calm": ["{team} golü buldu, golü atan {p}. {score}."],
        "shot_saved": ["{p} şutunu çekti, kaleci kurtarıyor.", "{p} denedi, kaleci yerinde."],
        "shot_off_target": ["{p} vurdu, top auta gidiyor.", "{p} şansını denedi, isabet yok."],
        "shot_blocked": ["{p} şutunu çekti, top savunmaya çarptı.", "{p} denedi, top bloke edildi."],
        "corner": ["{team} korner kazandı, topun başında {p}.", "Korner {team} lehine."],
        "foul": ["{p} faul yaptı, yerde kalan oyuncu {t}.", "Faul düdüğü: {p} ile {t} arasında temas."],
        "yellow_card": ["{team} oyuncusu {p} sarı kart görüyor.", "{p} kartla cezalandırıldı."],
        "red_card": ["Kırmızı kart! {p} oyundan atıldı, {team} 10 kişi.", "{p} kırmızı kart gördü!"],
        "penalty_awarded": [
            "Penaltı! {p} ceza sahasında yerde.",
            "Hakem beyaz noktayı gösteriyor, penaltı {team} lehine!",
        ],
        "free_kick": ["{p} tehlikeli bölgede serbest vuruşun başında."],
        "offside": ["Bayrak havada, {p} ofsaytta."],
        "substitution": ["{team} oyuncu değişikliği: {p} oyuna giriyor, {t} çıkıyor."],
        "stoppage_time": ["Uzatma süresi {extra} dakika."],
        "half_time": ["İlk yarı sona erdi. {score}."],
        "full_time": ["Maç sona erdi! Skor {score}."],
        "pass": ["{p} pasını verdi, topla buluşan {t}.", "{p} oyunu kurdu, top artık {t} ayağında."],
        "pass_intercepted": ["{p} pas denedi, araya girildi.", "{p} ileri oynamak istedi, top kesildi."],
        "tackle": ["{p} sert bir müdahaleyle topu kazandı."],
        "interception": ["{p} pası okudu ve araya girdi."],
    },
}

EXPLAIN = {
    "en": {
        "offside": "Offside means an attacker was closer to goal than the last defender when the ball was played to them.",
        "corner": "A corner is given when a defender is the last to touch the ball before it crosses their own goal line.",
        "yellow_card": "A yellow card is a caution. A second yellow in the same match means a red card.",
        "red_card": "A red card sends the player off; the team plays the rest of the match with one fewer.",
        "penalty_awarded": "A penalty is a free shot from 11 metres, given for a foul inside the box.",
        "free_kick": "A free kick restarts play after a foul; the wall must stand 9.15 metres away.",
        "stoppage_time": "Added time makes up for stoppages like injuries, substitutions and goals.",
        "substitution": "Each team can make a limited number of substitutions to bring in fresh players.",
    },
    "tr": {
        "offside": "Ofsayt: pas atıldığı anda hücumcu son savunmacıdan kaleye daha yakındaysa ofsayt olur.",
        "corner": "Korner: top son olarak bir savunmacıya değip kendi kale çizgisinden çıkarsa verilir.",
        "yellow_card": "Sarı kart bir uyarıdır. Aynı maçta ikinci sarı, kırmızı kart demektir.",
        "red_card": "Kırmızı kart gören oyuncu oyundan atılır, takım maçın kalanını bir eksik oynar.",
        "penalty_awarded": "Penaltı, ceza sahası içindeki faul için verilen 11 metreden serbest atıştır.",
        "free_kick": "Serbest vuruş faulden sonra oyunu başlatır; baraj 9,15 metre uzakta durmalıdır.",
        "stoppage_time": "Uzatma süresi; sakatlık, oyuncu değişikliği ve gol gibi duraksamaları telafi eder.",
        "substitution": "Her takım, taze oyuncu sokmak için sınırlı sayıda değişiklik yapabilir.",
    },
}


def play_by_play(
    event: MatchEvent, match: Match, score: dict, lang: str, style: str, club: str | None = None
) -> str:
    lang = _lang(lang)
    table = PBP[lang]
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
    speed = event.detail.get("ball_speed_kmh", 0)
    if style in ("hype", "calm", "beginner") and event.type == "shot" and speed >= 100:
        text += f" Top {speed} km/sa hızla gitti." if lang == "tr" else f" Struck at {speed} km/h!"
    if style == "hype" and event.type == "pass" and event.detail.get("difficulty", 0) >= 80:
        text += " Ne pas!" if lang == "tr" else " What a ball!"
    if style == "hype" and event.type in ("goal", "red_card", "penalty_awarded"):
        text = text.rstrip(".!") + "!!"
    if club and event.type in ("goal", "penalty_awarded", "red_card") and event.team:
        ours = event.team == club if event.type != "red_card" else event.team != club
        name = match.teams[club].name
        if ours:
            text = ("Eveeet! " if lang == "tr" else "Yes! ") + text
        else:
            text = (f"{name} için kötü haber: " if lang == "tr" else f"Bad news for {name}: ") + text
    return f"{event.display_minute} {text}"


def _tactical_suffix(event: MatchEvent, match: Match, lang: str) -> str:
    where = describe_location(event.x, event.y, event.team, lang)
    if event.type == "shot" and "distance_m" in event.detail:
        speed = event.detail.get("ball_speed_kmh")
        kmh = (f", {speed} km/sa" if lang == "tr" else f", {speed} km/h") if speed else ""
        return f"({event.detail['distance_m']} m{kmh}, {where})"
    if event.type == "pass" and "pass_distance_m" in event.detail:
        label = "zorluk" if lang == "tr" else "difficulty"
        return f"({event.detail['pass_distance_m']} m, {label} {event.detail['difficulty']}/100, {where})"
    if event.type == "goal":
        assist = match.player(event.target)
        if assist:
            label = "asist" if lang == "tr" else "assist"
            return f"({label}: {assist.short_name}, {where})"
    return f"({where})"


def explain(event_type: str, lang: str) -> str | None:
    return EXPLAIN[_lang(lang)].get(event_type)


def spatial(event: MatchEvent, match: Match, lang: str) -> str:
    lang = _lang(lang)
    team = event.possession
    if team is None:
        return ""
    name = match.teams[team].name
    x, y = (event.end_x, event.end_y) if event.end_x is not None else (event.x, event.y)
    where = describe_location(x, y, team, lang)
    if lang == "tr":
        return f"Top {name} ekibinde, {where}."
    return f"{name} in possession, {where}."


def color(event: MatchEvent, match: Match, sheet: FactSheet, lang: str, storylines: list[dict] = ()) -> str:
    """One or two sentences of analysis built only from facts on the sheet, shaped by the kind of moment."""
    lang = _lang(lang)
    tr = lang == "tr"
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
    parts: list[str] = [st["tr"] if tr else st["en"] for st in stories[:2]]
    has_tally = any(st["kind"] in ("brace", "hat_trick", "haul") for st in stories)
    if parts and event.type == "goal":
        pass  # the storyline already says what matters about this goal
    elif event.type == "goal" and player and not has_tally:
        goals = val(f"F-{event.player}-goals")
        if goals and int(goals) > 1:
            parts.append(
                f"{player.short_name} bu maçta {goals}. golünü attı."
                if tr
                else f"That's {goals} goals today for {player.short_name}."
            )
        if shots and on_target:
            parts.append(
                f"{name}: {shots} şut, {on_target} isabetli."
                if tr
                else f"{name} have now had {shots} shot{'s' if shots != '1' else ''}, {on_target} on target."
            )
    elif event.type in ("yellow_card", "red_card") and player:
        fouls = val(f"F-{event.player}-fouls")
        if fouls:
            parts.append(
                f"{player.short_name}, bugün {fouls} faul yaptı."
                if tr
                else f"{player.short_name} has committed {fouls} foul{'s' if fouls != '1' else ''} today."
            )
        cards = val(f"F-{team}-yellow_cards")
        if cards:
            parts.append(
                f"{name} toplam {cards} sarı kart gördü."
                if tr
                else f"{name} are on {cards} yellow card{'s' if cards != '1' else ''}."
            )
    elif event.type == "shot" and on_target:
        parts.append(
            f"{name} kaleyi {on_target} kez zorladı."
            if tr
            else f"That's {on_target} effort{'s' if on_target != '1' else ''} on target for {name}."
        )
    if momentum and len(parts) < 2:
        if tr:
            mood = momentum.replace(" on top", " üstün").replace("evenly balanced", "oyun dengeli")
            parts.append(f"Son beş dakikada {mood}.")
        else:
            parts.append(f"Over the last five minutes: {momentum}.")
    if poss and len(parts) < 2:
        parts.append(
            f"{name} topa %{poss} oranında sahip." if tr else f"{name} have had {poss}% of the ball."
        )
    return " ".join(parts[:2])


def stat_caption(sheet: FactSheet, lang: str) -> str:
    """Head-to-head line such as "Possession 54-46 · Shots 7-5"; falls back to listing facts."""
    lang = _lang(lang)
    labels = {
        "possession_pct": ("Possession %", "Topa sahip olma %"),
        "shots": ("Shots", "Şut"),
        "shots_on_target": ("On target", "İsabetli şut"),
        "corners": ("Corners", "Korner"),
    }
    pairs = []
    for stat, (en, tr) in labels.items():
        home, away = sheet.facts.get(f"F-home-{stat}"), sheet.facts.get(f"F-away-{stat}")
        if home and away:
            pairs.append(f"{tr if lang == 'tr' else en} {home.value}-{away.value}")
    if not pairs:
        pairs = [f"{f.label}: {f.value}" for f in list(sheet.facts.values())[:4]]
    return ("İstatistik: " if lang == "tr" else "Stats: ") + " · ".join(pairs)


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
    "haul",
)


def _story_rank(story: dict) -> int:
    return STORY_PRIORITY.index(story["kind"]) if story["kind"] in STORY_PRIORITY else len(STORY_PRIORITY)


def recap(match: Match, snapshot: dict, lang: str, final: bool) -> str:
    lang = _lang(lang)
    stories = sorted(snapshot.get("storylines", []), key=_story_rank)
    story = (" " + (stories[0]["tr"] if lang == "tr" else stories[0]["en"])) if stories else ""
    home, away = match.teams["home"].name, match.teams["away"].name
    s = snapshot["score"]
    th, ta = snapshot["teams"]["home"], snapshot["teams"]["away"]
    goals = [m for m in snapshot["key_moments"] if m["type"] == "goal"]
    if lang == "tr":
        head = "Maç sonu" if final else "İlk yarı özeti"
        scorers = ", ".join(f"{m['player']} {m['minute']}" for m in goals) or "gol yok"
        return (
            f"{head}: {home} {s['home']}-{s['away']} {away}.{story} Goller: {scorers}. "
            f"Topa sahip olma %{th['possession_pct']}-%{ta['possession_pct']}, "
            f"şutlar {th['shots']}-{ta['shots']} (isabetli {th['shots_on_target']}-{ta['shots_on_target']})."
        )
    head = "Full time" if final else "Half-time report"
    scorers = ", ".join(f"{m['player']} {m['minute']}" for m in goals) or "no goals"
    return (
        f"{head}: {home} {s['home']}-{s['away']} {away}.{story} Goals: {scorers}. "
        f"Possession {th['possession_pct']}%-{ta['possession_pct']}%, "
        f"shots {th['shots']}-{ta['shots']} ({th['shots_on_target']}-{ta['shots_on_target']} on target)."
    )
