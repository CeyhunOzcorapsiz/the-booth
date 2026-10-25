"""Browser tests: the real UI against a real server.

Needs ``pip install -e ".[e2e]"`` and a browser (``playwright install chromium``, or set
``BOOTH_E2E_CHANNEL=msedge`` / ``chrome`` to use an installed one). Skipped when Playwright is missing.
"""

from __future__ import annotations

import socket
import threading
import time

import pytest

playwright_api = pytest.importorskip("playwright.sync_api")

import os  # noqa: E402

import uvicorn  # noqa: E402

from booth.api import app  # noqa: E402

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def base_url():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="module")
def browser():
    with playwright_api.sync_playwright() as p:
        channel = os.getenv("BOOTH_E2E_CHANNEL") or None
        try:
            instance = p.chromium.launch(channel=channel)
        except Exception as exc:  # no browser installed
            pytest.skip(f"no browser available: {exc}")
        yield instance
        instance.close()


@pytest.fixture
def page(browser):
    context = browser.new_context(viewport={"width": 1440, "height": 900}, locale="en-GB")
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    yield page
    context.close()
    assert not errors, errors


def test_setup_dialog_then_live_broadcast(page, base_url):
    page.goto(base_url)
    dialog = page.locator("#setup")
    assert dialog.is_visible()
    page.select_option("#speed", "90")
    page.fill("#start", "80")
    page.click("#goLive")
    page.wait_for_selector("#feed .segment-text", timeout=15_000)
    assert page.locator("#liveLabel").inner_text() in ("LIVE", "FULL TIME")
    assert page.locator("#actors .actor").count() >= 20
    playwright_api.expect(page.locator("#trace li").nth(3)).to_be_attached()
    assert page.locator("#agent-director .count").inner_text() != "0"


def test_storyline_and_score_on_the_demo_match(page, base_url):
    page.goto(f"{base_url}/?live=1&seed=119&lang=en&style=hype&start=81&speed=10")
    playwright_api.expect(page.locator("#storyline")).to_contain_text("fought back", timeout=20_000)
    assert page.locator("#homeScore").inner_text() in ("2", "3")


def test_compare_view_shows_three_verified_broadcasts(page, base_url):
    page.goto(f"{base_url}/?view=compare&seed=119")
    page.wait_for_selector(".compare-col .segment-text", timeout=15_000)
    columns = page.locator(".compare-col")
    assert columns.count() == 3
    texts = [columns.nth(i).locator(".segment-text").first.inner_text() for i in range(3)]
    assert len(set(texts)) == 3
    assert page.locator(".compare-col .verified").count() >= 3


def test_ask_the_booth_answers_with_sources(page, base_url):
    page.goto(f"{base_url}/?live=1&seed=119&start=85&speed=90")
    page.wait_for_selector("#feed .segment-text", timeout=15_000)
    page.fill("#question", "Who has more possession?")
    page.click("#askForm button")
    page.wait_for_selector("#answer .evidence", timeout=10_000)
    assert "%" in page.locator("#answer").inner_text() or "possession" in page.locator("#answer").inner_text()


def close_setup(page):
    """The setup dialog opens after the page has loaded its data; wait for it before dismissing it."""
    dialog = page.locator("#setup")
    playwright_api.expect(dialog).to_be_visible()
    page.keyboard.press("Escape")
    playwright_api.expect(dialog).to_be_hidden()


def test_interface_switches_to_turkish_and_remembers_it(page, base_url):
    page.goto(base_url)
    close_setup(page)
    assert page.locator(".control-room h2").inner_text() == "Control room"
    page.click("#uiLang")
    assert page.locator(".control-room h2").inner_text() == "Kontrol odası"
    assert page.locator("html").get_attribute("lang") == "tr"
    page.reload()
    close_setup(page)
    assert page.locator(".control-room h2").inner_text() == "Kontrol odası"
    assert page.locator("#goLive").inner_text() == "Yayına başla"
    page.click("#uiLang")
    assert page.locator(".control-room h2").inner_text() == "Control room"
