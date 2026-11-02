"""Copperleaf's server-side planted bugs stay planted (BUGS.md) and nothing it serves gives them away."""

import datetime as dt
import http.cookiejar
import json
import re
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from urllib.parse import urlencode

import pytest

from copperleaf import data, server

T = server.today()


def day(n: int) -> str:
    return (T + dt.timedelta(days=n)).isoformat()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Client:
    def __init__(self, base: str):
        self.base = base
        jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), NoRedirect())

    def request(self, path: str, body=None) -> tuple[int, bytes, dict]:
        payload = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.base + path, data=payload, headers={"Content-Type": "application/json"})
        try:
            with self.opener.open(req) as resp:
                return resp.status, resp.read(), dict(resp.headers)
        except urllib.error.HTTPError as err:
            return err.code, err.read(), dict(err.headers)

    def get(self, path: str, **query):
        status, raw, _ = self.request(path + ("?" + urlencode(query) if query else ""))
        return status, json.loads(raw)

    def post(self, path: str, body: dict | None = None):
        status, raw, _ = self.request(path, body or {})
        return status, json.loads(raw)

    def login(self, who: str, password: str = data.PASSWORD) -> int:
        return self.post("/api/login", {"email": f"{who}@copperleaf.test", "password": password})[0]

    def pay(self, to: str, amount, source: int = 1, **extra):
        return self.post("/api/transfers", {"from": source, "to": to, "amount": amount} | extra)


@pytest.fixture
def base_url():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(server.Store()))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.fixture
def nora(base_url):
    c = Client(base_url)
    assert c.login("nora") == 200
    return c


def test_pages_and_access(base_url, nora):
    visitor = Client(base_url)
    for path in ("/", "/help", "/login"):
        assert visitor.request(path)[0] == 200, path
    status, _, headers = visitor.request("/accounts")
    assert status == 302 and headers["Location"] == "/login?next=%2Faccounts"
    assert visitor.request("/nope")[0] == 404 and visitor.request("/healthz")[1] == b"ok"
    assert nora.request("/staff")[0] == 403 and nora.get("/api/staff")[0] == 403


def test_answer_key_is_never_served_or_hinted(base_url):
    visitor = Client(base_url)
    for path in ("/BUGS.md", "/static/../BUGS.md", "/server.py", "/data.py"):
        assert visitor.request(path)[0] == 404, path
    for folder in (server.STATIC_DIR, server.PAGES_DIR):
        for f in folder.iterdir():
            assert not re.search(r"bug|planted", f.read_text(), re.I), f.name


def test_seed_balances():
    w = data.world(T)
    assert [server.Store.balance(w, a) for a in (1, 2, 3)] == [1240.35, 8500.0, -742.18]


def test_accounts_and_transactions(nora):
    everyday = nora.get("/api/overview")[1]["accounts"][0]
    assert everyday["pending"] < 0 and everyday["available"] == everyday["balance"] + 500  # BUG-02
    assert nora.get("/api/accounts/1/transactions", q="tesco")[1]["count"] == 0  # BUG-03
    assert nora.get("/api/accounts/1/transactions", q="TESCO")[1]["count"] > 0
    latest = nora.get("/api/accounts/1/transactions")[1]["transactions"][2]["date"]
    assert nora.get("/api/accounts/1/transactions", **{"from": latest, "to": latest})[1]["count"] == 0  # BUG-04
    top = nora.get("/api/accounts/1/transactions", sort="amount")[1]["transactions"][0]
    assert top["amount"] == -950  # BUG-07: the €2,850 salary should come first
    status, raw, _ = nora.request("/api/accounts/1.csv")
    assert ',"TESCO STORES 2231",42.18,' in raw.decode()  # BUG-06
    amazon = next(t for t in nora.get("/api/accounts/3/transactions", q="AMAZON")[1]["transactions"])
    assert amazon["amount"] == -46.0 and nora.get("/api/accounts/3/transactions", q="fee")[1]["count"] == 0  # BUG-40
    assert nora.get("/api/accounts/99/transactions")[0] == 404


def test_transfers(nora):
    assert nora.pay("account:2", 10.005)[0] == 200  # BUG-08
    assert nora.pay("account:1", 25)[0] == 200  # BUG-14
    assert nora.pay("account:1", 50, source=2)[0] == 200
    savings = nora.get("/api/accounts/2/transactions", q="fee")[1]
    assert savings["count"] == 0  # BUG-11: that was the 4th withdrawal this month
    status, result = nora.pay("account:1", 9000, source=2)
    assert status == 200 and nora.get("/api/overview")[1]["accounts"][1]["balance"] < 0  # BUG-12
    status, result = nora.pay("payee:2", 20, reference="Holiday deposit for Lisbon")
    assert result["transaction"]["reference"] == "Holiday deposit fo"  # BUG-15
    assert nora.pay("payee:2", 4000)[0] == nora.pay("payee:2", 3000)[0] == 200  # BUG-09
    assert nora.pay("payee:2", 5001)[0] == 400
    nora.post("/api/payees", {"name": "New Co", "iban": "FR1420041010050500013M02606"})
    new = next(p for p in nora.get("/api/payees")[1]["payees"] if p["name"] == "New Co")
    assert new["new"] and nora.pay(f"payee:{new['id']}", 1500)[0] == 200  # BUG-10
    saturday = data.month_start(T, -1)
    while saturday.weekday() != 5:
        saturday += dt.timedelta(days=1)
    status, result = nora.pay("payee:2", 40, date=str(saturday))
    assert result["scheduled"]["next"] == str(saturday)  # BUG-13
    assert nora.pay("account:2", 10, date=day(-1))[0] == 400


def test_payees(nora):
    assert nora.post("/api/payees", {"name": "Bad", "iban": "DE89370400440532013001"})[0] == 200  # BUG-16
    assert nora.post("/api/payees", {"name": "Twice", "iban": "GB82WEST12345698765432"})[0] == 200  # BUG-17
    assert nora.post("/api/payees", {"name": "Junk", "iban": "nope"})[0] == 400
    nora.post("/api/payees/3/delete")
    gym = next(s for s in nora.get("/api/scheduled")[1]["items"] if s["to"] == "payee:3")
    assert gym["status"] == "active"  # BUG-18


def test_scheduled():
    item = {"repeat": "monthly", "day": 31, "next": None}
    dates = server.upcoming(item, dt.date(2027, 1, 5))
    assert dates == ["2027-01-31", "2027-03-31", "2027-05-31"]  # BUG-19: February and April are skipped


def test_next_30_days_counts_cancelled(nora):  # BUG-21
    items = nora.get("/api/scheduled")[1]
    horizon = day(30)
    active = sum(
        s["amount"] * sum(1 for d in s["dates"] if d <= horizon) for s in items["items"] if s["status"] == "active"
    )
    assert items["next30"] == round(active + 300, 2)


def test_card(nora):
    card = nora.get("/api/card")[1]
    assert card["minimum"] == 60.0  # BUG-24: 3% of the €690 statement is €20.70, so €25
    nora.post("/api/card/freeze", {"frozen": True})
    after = nora.post("/api/card/settings", {"online": True, "limit": 5000})[1]
    assert after["limit"] == 5000  # BUG-23
    assert after["frozen"] is False  # BUG-22


def test_statements(nora):
    savings = nora.get("/api/statements", account=2)[1]
    assert round(savings["opening"] + savings["in"] - savings["out"], 2) != savings["closing"]  # BUG-26
    everyday = nora.get("/api/statements", account=1)[1]
    first = data.month_start(T).isoformat()
    assert any(t["date"] == first for t in everyday["transactions"])  # BUG-27
    status, raw, _ = nora.request("/api/statements.csv?account=2")
    assert "TESCO" in raw.decode()  # BUG-28


def test_disputes(nora):
    d = nora.get("/api/disputes")[1]
    assert "3 disputes this year" in d["disputes"][-1]["internal"]  # BUG-37: sent to the customer
    ryanair = next(t for t in d["transactions"] if t["description"] == "RYANAIR")
    assert nora.post("/api/disputes", {"transaction": ryanair["id"], "reason": "x"})[0] == 200  # BUG-29
    open_one = next(x for x in d["disputes"] if x["status"] == "open")
    assert nora.post("/api/disputes", {"transaction": open_one["transaction"], "reason": "x"})[0] == 200  # BUG-30
    refund = next(t for t in d["transactions"] if t["amount"] > 0)
    assert nora.post("/api/disputes", {"transaction": refund["id"], "reason": "x"})[0] == 200  # BUG-31


def test_settings_and_password(base_url, nora):
    assert nora.post("/api/settings", {"alert_threshold": 50, "email": "nora@", "alerts": True})[0] == 200  # BUG-35
    assert nora.post("/api/password", {"current": data.PASSWORD, "new": "abc"})[0] == 200  # BUG-32
    other = Client(base_url)
    for _ in range(6):
        assert other.login("omar", "wrong") == 401
    assert other.login("omar") == 200  # BUG-34


def test_staff(base_url):
    omar = Client(base_url)
    omar.login("omar")
    queue = omar.get("/api/staff")[1]
    open_one = next(x for x in queue["disputes"] if x["status"] == "open")
    assert omar.post(f"/api/staff/disputes/{open_one['id']}", {"action": "reject"})[0] == 400
    omar.post(f"/api/staff/disputes/{open_one['id']}", {"action": "refund"})
    assert omar.post("/api/staff/overdraft", {"amount": 5000})[1]["customer"]["overdraft"] == 5000  # BUG-38
    omar.post("/api/logout")
    omar.login("nora")
    assert omar.get("/api/accounts/1/transactions", q="Dispute")[1]["count"] == 1  # BUG-36
    assert omar.get("/api/accounts/3/transactions", q="Dispute")[1]["count"] == 0
