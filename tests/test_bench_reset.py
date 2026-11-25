"""POST /__bench/reset puts the site back to its seed, so every benchmark scan starts from the same data."""

import copy
import datetime as dt
import http.cookiejar
import threading
import types
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from copperleaf import server

TOKEN = "bench-test-token-0123456789"
NOW = 1_800_000_000.0  # one fixed clock: the seed is dated from "now"


@pytest.fixture
def fixed_clock(monkeypatch):
    """Two seeds built at different moments differ only by the clock; pin it so they can be compared."""
    if hasattr(server, "time"):
        real = server.time
        monkeypatch.setattr(server, "time", types.SimpleNamespace(time=lambda: NOW, monotonic=real.monotonic))
    when = dt.datetime.fromtimestamp(NOW, dt.UTC)
    if hasattr(server, "today"):
        monkeypatch.setattr(server, "today", lambda: when.date())
    if hasattr(server, "now_utc"):
        monkeypatch.setattr(server, "now_utc", lambda: when)


def seed(store, sess):
    """The data one visitor sees and changes (every visitor gets their own copy of the seed)."""
    return store.world(sess)


def norm(x):
    return x


def edit_everything(x) -> None:
    """Change every list and dict in ``x``, however deep: whatever a scan could have edited."""
    if isinstance(x, dict):
        for v in list(x.values()):
            edit_everything(v)
        x["edited"] = True
    elif isinstance(x, list):
        for v in list(x):
            edit_everything(v)
        x.append("edited")


def test_a_reset_after_edits_gives_the_seed_again(fixed_clock):
    store = server.Store()
    sid, sess = store.session(None)
    before = copy.deepcopy(seed(store, sess))
    edit_everything(seed(store, sess))
    _, other = store.session(None)
    edit_everything(seed(store, other))

    assert store.reset() == 2
    assert not store.sessions
    new_sid, fresh = store.session(sid)  # the old cookie is unknown now: a new visitor
    assert new_sid != sid
    assert norm(seed(store, fresh)) == norm(before)
    again = server.Store()
    assert norm(seed(again, again.session(None)[1])) == norm(before)  # nothing leaked into the seed itself


@pytest.fixture
def site():
    store = server.Store()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(store, reset_token=TOKEN))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield store, f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def call(base: str, path: str, token: str | None = None, opener=None, method: str = "POST") -> int:
    headers = {"Content-Type": "application/json"} | ({server.RESET_HEADER: token} if token is not None else {})
    req = urllib.request.Request(base + path, data=b"{}" if method == "POST" else None, headers=headers, method=method)
    try:
        with (opener or urllib.request.build_opener()).open(req) as resp:
            return resp.status
    except urllib.error.HTTPError as err:
        return err.code


def test_the_endpoint_needs_the_token(site):
    store, base = site
    jar = http.cookiejar.CookieJar()
    visitor = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    call(base, "/", opener=visitor, method="GET")
    mine = {c.value for c in jar} & store.sessions.keys()
    assert mine, "the visitor has a session"

    for token in (None, "", "wrong-token-0123456789"):
        assert call(base, server.RESET_PATH, token) != 200
    assert call(base, server.RESET_PATH, TOKEN, method="GET") != 200
    assert mine <= store.sessions.keys(), "nothing was reset"

    assert call(base, server.RESET_PATH, TOKEN) == 200
    assert not store.sessions
    old = {c.name: c.value for c in jar}
    call(base, "/", opener=visitor, method="GET")
    assert {c.name: c.value for c in jar} != old, "the visitor starts over with a fresh session"


def test_off_without_a_token(monkeypatch):
    assert server.bench_token({}) is None
    assert server.bench_token({server.RESET_ENV: "short"}) is None
    assert server.bench_token({server.RESET_ENV: TOKEN}) == TOKEN
    assert not server.token_ok(TOKEN, None)
    assert not server.token_ok(None, TOKEN)
    assert server.token_ok(TOKEN, TOKEN)
