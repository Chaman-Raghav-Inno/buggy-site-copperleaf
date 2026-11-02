"""Copperleaf Bank: a demo online bank with planted functional bugs, for checking what the AI QA Scanner finds.

The bugs are listed in BUGS.md (the answer key), which is never served. Comments marking a planted bug (BUG-nn)
only appear in server-side code; the pages and scripts the scanner reads carry none.

Each visitor (cookie) gets a private copy of the demo world, kept in memory, so parallel scans never see each
other's changes. Logging in as the customer or the staff member in the same browser shares that world.
"""

import datetime as dt
import hmac
import html
import json
import os
import re
import secrets
import threading
from collections import OrderedDict
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

from . import data

HERE = Path(__file__).resolve().parent
PAGES_DIR = HERE / "pages"
STATIC_DIR = HERE / "static"
STATIC_TYPES = {".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml"}
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Content-Security-Policy": (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'"
    ),
}
MAX_BODY = 1024 * 1024
MAX_SESSIONS = 1500
TXN_PAGE = 10
IBAN_FORMAT = re.compile(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}")
EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")

# path -> (page, title, who may open it)
PAGES = {
    "/": ("landing", "Welcome", None),
    "/login": ("login", "Log in", None),
    "/help": ("help", "Fees and limits", None),
    "/accounts": ("accounts", "Accounts", "customer"),
    "/account": ("account", "Account", "customer"),
    "/transfer": ("transfer", "Move money", "customer"),
    "/payees": ("payees", "Payees", "customer"),
    "/scheduled": ("scheduled", "Scheduled payments", "customer"),
    "/card": ("card", "Card", "customer"),
    "/statements": ("statements", "Statements", "customer"),
    "/disputes": ("disputes", "Disputes", "customer"),
    "/settings": ("settings", "Settings", "customer"),
    "/staff": ("staff", "Staff desk", "staff"),
}


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def today() -> dt.date:
    return dt.datetime.now(dt.UTC).date()


def _text(body: dict, key: str, limit: int = 200) -> str:
    value = body.get(key, "")
    return value.strip()[:limit] if isinstance(value, str) else ""


def _date(value, message: str) -> dt.date:
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError:
        raise ApiError(400, message) from None


def _amount(value, message: str = "Enter an amount.") -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not 0 < value <= 1_000_000:
        raise ApiError(400, message)
    return float(value)  # BUG-08: amounts with more than two decimals are not refused


def money(x: float) -> float:
    return round(x + 1e-9, 2)


def iban_ok(iban: str) -> bool:
    return bool(IBAN_FORMAT.fullmatch(iban))  # BUG-16: the mod-97 check digits are never checked


def upcoming(item: dict, start: dt.date, count: int = 3) -> list[str]:
    """The next dates a scheduled payment leaves the account, from start onwards."""
    if item["repeat"] == "once":
        return [item["next"]] if item["next"] and item["next"] >= start.isoformat() else []
    out, y, m = [], start.year, start.month
    while len(out) < count:
        try:
            d = dt.date(y, m, item["day"])  # BUG-19: months without that day are skipped, not paid on their last day
            if d >= start:
                out.append(d.isoformat())
        except ValueError:
            pass
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


class Store:
    def __init__(self):
        self.lock = threading.Lock()
        self.sessions: OrderedDict[str, dict] = OrderedDict()

    def session(self, sid: str | None) -> tuple[str, dict]:
        if sid and sid in self.sessions:
            self.sessions.move_to_end(sid)
            return sid, self.sessions[sid]
        sid = secrets.token_urlsafe(24)
        self.sessions[sid] = {"world": None, "user": None}
        while len(self.sessions) > MAX_SESSIONS:
            self.sessions.popitem(last=False)
        return sid, self.sessions[sid]

    @staticmethod
    def world(sess: dict) -> dict:
        if sess["world"] is None:
            sess["world"] = data.world(today())
        return sess["world"]

    def user(self, sess: dict) -> dict | None:
        if sess["user"] is None:
            return None
        return next((u for u in self.world(sess)["users"] if u["id"] == sess["user"]), None)

    def signed_in(self, sess: dict, role: str = "customer") -> dict:
        user = self.user(sess)
        if not user:
            raise ApiError(401, "Please log in.")
        if user["role"] != role:
            raise ApiError(403, "That is for " + ("customers." if role == "customer" else "bank staff."))
        return self.world(sess)

    def me(self, sess: dict) -> dict:
        user = self.user(sess)
        out = {"today": self.world(sess)["today"]}
        return out | {"user": {k: user[k] for k in ("id", "name", "email", "role")} if user else None}

    def login(self, sess: dict, body: dict) -> dict:
        w = self.world(sess)
        email = _text(body, "email").lower()
        u = next((u for u in w["users"] if u["email"] == email), None)
        password = body.get("password")
        # BUG-34: the lockout after 5 wrong passwords is never applied
        if not (u and isinstance(password, str)) or not hmac.compare_digest(
            u["hash"], data.password_hash(password, bytes.fromhex(u["salt"]))
        ):
            if u:
                u["failed"] += 1
            raise ApiError(401, "Incorrect email or password.")
        u["failed"] = 0
        sess["user"] = u["id"]
        return self.me(sess)

    # accounts and transactions

    @staticmethod
    def account(w: dict, aid: int) -> dict:
        found = next((a for a in w["accounts"] if a["id"] == aid), None)
        if not found:
            raise ApiError(404, "We couldn't find that account.")
        return found

    @staticmethod
    def balance(w: dict, aid: int, until: str | None = None) -> float:
        return money(
            sum(
                t["amount"]
                for t in w["transactions"]
                if t["account"] == aid and t["status"] == "posted" and (until is None or t["date"] < until)
            )
        )

    def summary(self, w: dict, a: dict) -> dict:
        bal = self.balance(w, a["id"])
        pending = money(
            sum(t["amount"] for t in w["transactions"] if t["account"] == a["id"] and t["status"] == "pending")
        )
        out = {k: a[k] for k in ("id", "name", "type", "number")} | {"balance": bal, "pending": pending}
        if a["type"] == "card":
            out |= {"credit_limit": a["credit_limit"], "available": money(a["credit_limit"] + bal + pending)}
        else:
            out |= {"overdraft": a["overdraft"], "available": money(bal + a["overdraft"])}  # BUG-02: ignores pending
        return out

    def overview(self, sess: dict) -> dict:
        w = self.signed_in(sess)
        recent = sorted(
            (t for t in w["transactions"] if t["type"] != "opening"), key=lambda t: (t["date"], t["id"]), reverse=True
        )[:6]
        names = {a["id"]: a["name"] for a in w["accounts"]}
        return {
            "accounts": [self.summary(w, a) for a in w["accounts"]],
            "recent": [t | {"account_name": names[t["account"]]} for t in recent],
            "name": self.user(sess)["name"].split()[0],
        }

    def transactions(self, sess: dict, aid: int, query: dict) -> dict:
        w = self.signed_in(sess)
        a = self.account(w, aid)
        arg = {k: (query.get(k) or [""])[0] for k in query}
        rows = [t for t in w["transactions"] if t["account"] == aid and t["type"] != "opening"]
        if arg.get("q"):
            rows = [t for t in rows if arg["q"].strip() in t["description"]]  # BUG-03: case-sensitive search
        if arg.get("from"):
            rows = [t for t in rows if t["date"] >= str(_date(arg["from"], "Bad start date."))]
        if arg.get("to"):
            rows = [t for t in rows if t["date"] < str(_date(arg["to"], "Bad end date."))]  # BUG-04: misses that day
        if arg.get("sort") == "amount":
            rows.sort(key=lambda t: str(abs(t["amount"])), reverse=True)  # BUG-07: sorts the digits as text
        else:
            rows.sort(key=lambda t: (t["status"] == "pending", t["date"], t["id"]), reverse=True)
        try:
            page = max(1, int(arg.get("page") or 1))
        except ValueError:
            raise ApiError(400, "Bad page.") from None
        pages = max(1, -(-len(rows) // TXN_PAGE))
        totals = {
            "in": money(sum(t["amount"] for t in rows if t["amount"] > 0 and t["status"] == "posted")),
            "out": money(-sum(t["amount"] for t in rows if t["amount"] < 0 and t["status"] == "posted")),
        }
        start = (page - 1) * TXN_PAGE
        return {
            "account": self.summary(w, a),
            "transactions": rows[start : start + TXN_PAGE],
            "page": page,
            "pages": pages,
            "count": len(rows),
            "totals": totals,
        }

    def transactions_csv(self, sess: dict, aid: int, query: dict) -> bytes:
        first = self.transactions(sess, aid, query | {"page": ["1"]})
        rows = list(first["transactions"])
        for p in range(2, first["pages"] + 1):
            rows += self.transactions(sess, aid, query | {"page": [str(p)]})["transactions"]
        lines = ["Date,Description,Amount (EUR),Status"]
        for t in rows:
            lines.append(f'{t["date"]},"{t["description"]}",{abs(t["amount"]):.2f},{t["status"]}')  # BUG-06: no sign
        return ("\n".join(lines) + "\n").encode()

    # payees

    def payees(self, sess: dict) -> dict:
        w = self.signed_in(sess)
        now = dt.datetime.combine(dt.date.fromisoformat(w["today"]), dt.datetime.now(dt.UTC).time())
        out = []
        for p in w["payees"]:
            new = now - dt.datetime.fromisoformat(p["created"]) < dt.timedelta(hours=24)
            out.append(p | {"new": new})
        return {"payees": out}

    def add_payee(self, sess: dict, body: dict) -> dict:
        w = self.signed_in(sess)
        name = _text(body, "name", 60)
        if not name:
            raise ApiError(400, "Enter the payee's name.")
        iban = re.sub(r"\s", "", _text(body, "iban", 60)).upper()
        if not iban_ok(iban):
            raise ApiError(400, "That IBAN isn't valid. Check it and try again.")
        # BUG-17: a payee with the same IBAN can be added again
        pretty = " ".join(iban[i : i + 4] for i in range(0, len(iban), 4))
        now = dt.datetime.combine(dt.date.fromisoformat(w["today"]), dt.datetime.now(dt.UTC).time())
        w["payees"].append(
            {
                "id": w["next_id"],
                "name": name,
                "iban": pretty,
                "reference": _text(body, "reference", data.REFERENCE_MAX),
                "created": now.isoformat(),
            }
        )
        w["next_id"] += 1
        return self.payees(sess)

    def delete_payee(self, sess: dict, pid: int) -> dict:
        w = self.signed_in(sess)
        p = next((p for p in w["payees"] if p["id"] == pid), None)
        if not p:
            raise ApiError(404, "We couldn't find that payee.")
        w["payees"].remove(p)  # BUG-18: their standing orders and scheduled payments keep running
        return self.payees(sess)

    # transfers

    def transfer(self, sess: dict, body: dict) -> dict:
        w = self.signed_in(sess)
        now = dt.date.fromisoformat(w["today"])
        try:
            src = self.account(w, int(body.get("from")))
        except (TypeError, ValueError):
            raise ApiError(400, "Choose the account to pay from.") from None
        if src["type"] == "card":
            raise ApiError(400, "You can't send money from a credit card.")
        target = str(body.get("to") or "")
        kind, _, tid = target.partition(":")
        if kind == "account":
            dest = self.account(w, int(tid) if tid.isdigit() else 0)
            to_name = dest["name"]
            # BUG-14: paying an account into itself is not refused
        elif kind == "payee":
            payee = next((p for p in w["payees"] if str(p["id"]) == tid), None)
            if not payee:
                raise ApiError(400, "Choose who to pay.")
            to_name = payee["name"]
        else:
            raise ApiError(400, "Choose who to pay.")
        amount = _amount(body.get("amount"))
        when = _date(body.get("date") or w["today"], "Choose a date.")
        if when < now:
            raise ApiError(400, "The date can't be in the past.")
        repeat = body.get("repeat") if body.get("repeat") in ("once", "monthly") else "once"
        reference = _text(body, "reference", 200)[: data.REFERENCE_MAX]  # BUG-15: longer references are cut silently
        if kind == "payee" and amount > data.DAILY_PAYEE_LIMIT:  # BUG-09: today's earlier payments aren't counted
            raise ApiError(400, "That's over your daily limit of €5,000 to payees.")
        # BUG-10: payees added in the last 24 hours have no €1,000 limit
        if when > now or repeat == "monthly":
            # BUG-13: a date at the weekend is kept, not moved to the next working day
            item = {
                "id": w["next_id"],
                "from": src["id"],
                "to": target,
                "to_name": to_name,
                "amount": amount,
                "repeat": repeat,
                "day": when.day if repeat == "monthly" else None,
                "next": when.isoformat(),
                "reference": reference,
                "status": "active",
            }
            w["next_id"] += 1
            w["scheduled"].append(item)
            return {"done": "scheduled", "scheduled": item | {"dates": upcoming(item, when)}}
        if src["type"] == "everyday" and amount > self.summary(w, src)["available"]:
            raise ApiError(400, "You don't have enough money available for that.")
        # BUG-12: savings can go below zero
        fee = 0.0  # BUG-11: the €2 fee from the 4th savings withdrawal in a month is never charged

        def post(account, description, value, **extra):
            t = {
                "id": w["next_id"],
                "account": account,
                "date": w["today"],
                "description": description,
                "amount": money(value),
                "type": "transfer",
                "status": "posted",
                "reference": reference,
                "foreign": "",
            } | extra
            w["next_id"] += 1
            w["transactions"].append(t)
            return t

        out = post(src["id"], f"To {to_name}", -amount, payee=kind == "payee")
        if kind == "account":
            post(int(tid), f"From {src['name']}", amount)
        if fee:
            post(src["id"], "Savings withdrawal fee", -fee)
        return {"done": "sent", "transaction": out, "balance": self.balance(w, src["id"])}

    # scheduled payments

    def scheduled(self, sess: dict) -> dict:
        w = self.signed_in(sess)
        now = dt.date.fromisoformat(w["today"])
        horizon = (now + dt.timedelta(days=30)).isoformat()
        items, total = [], 0.0
        for s in w["scheduled"]:
            dates = upcoming(s, now + dt.timedelta(days=1))
            items.append(s | {"dates": dates, "next": dates[0] if dates else s["next"]})
            total += s["amount"] * sum(1 for d in dates if d <= horizon)  # BUG-21: cancelled payments are counted
        names = {a["id"]: a["name"] for a in w["accounts"]}
        return {"items": [i | {"from_name": names[i["from"]]} for i in items], "next30": money(total)}

    def cancel_scheduled(self, sess: dict, sid: int) -> dict:
        w = self.signed_in(sess)
        s = next((s for s in w["scheduled"] if s["id"] == sid), None)
        if not s:
            raise ApiError(404, "We couldn't find that payment.")
        if s["status"] != "active":
            raise ApiError(409, "That payment is already cancelled.")
        s["status"] = "cancelled"
        return self.scheduled(sess)

    # card

    def card(self, sess: dict) -> dict:
        w = self.signed_in(sess)
        a = self.account(w, 3)
        s = self.summary(w, a)
        minimum = max(data.MIN_PAYMENT_FLOOR, data.MIN_PAYMENT_RATE * a["credit_limit"])  # BUG-24: of the balance
        return w["card"] | {
            "owed": -s["balance"],
            "available": s["available"],
            "credit_limit": a["credit_limit"],
            "statement_balance": a["statement_balance"],
            "minimum": money(minimum),
            "due": a["due"],
        }

    def freeze(self, sess: dict, body: dict) -> dict:
        w = self.signed_in(sess)
        w["card"]["frozen"] = bool(body.get("frozen"))
        return self.card(sess)

    def card_settings(self, sess: dict, body: dict) -> dict:
        w = self.signed_in(sess)
        limit = _amount(body.get("limit"), "Enter a monthly limit.")  # BUG-23: €50 to €2,000 isn't enforced
        # BUG-22: the settings are rebuilt from scratch, so saving them unfreezes the card
        w["card"].update(online=bool(body.get("online")), limit=money(limit), frozen=bool(body.get("frozen", False)))
        return self.card(sess)

    # statements

    def statement(self, sess: dict, aid: int, month: str) -> dict:
        w = self.signed_in(sess)
        a = self.account(w, aid)
        now = dt.date.fromisoformat(w["today"])
        months = [data.month_start(now, k).isoformat()[:7] for k in (1, 2, 3)]
        month = month or months[0]
        if month not in months:
            raise ApiError(404, "Statements are available for the last three months.")
        start = dt.date.fromisoformat(month + "-01")
        end = data.month_start(start, -1)
        rows = [
            t
            for t in w["transactions"]
            if t["account"] == aid
            and t["status"] == "posted"
            and t["type"] != "opening"
            and start.isoformat() <= t["date"] <= end.isoformat()
        ]
        # BUG-27: the first day of the next month is included
        opening = self.balance(w, aid, start.isoformat())
        money_in = sum(t["amount"] for t in rows if t["amount"] > 0 and t["type"] != "interest")  # BUG-26
        money_out = -sum(t["amount"] for t in rows if t["amount"] < 0)
        closing = opening + sum(t["amount"] for t in rows)
        return {
            "account": {k: a[k] for k in ("id", "name", "number", "type")},
            "month": month,
            "months": months,
            "opening": money(opening),
            "in": money(money_in),
            "out": money(money_out),
            "closing": money(closing),
            "transactions": sorted(rows, key=lambda t: (t["date"], t["id"])),
        }

    def statement_csv(self, sess: dict, aid: int, month: str) -> bytes:
        s = self.statement(sess, aid, month)
        w = self.world(sess)
        start, end = s["month"] + "-01", data.month_start(dt.date.fromisoformat(s["month"] + "-01"), -1).isoformat()
        rows = [
            t
            for t in w["transactions"]
            if t["status"] == "posted" and t["type"] != "opening" and start <= t["date"] < end
        ]
        # BUG-28: every account's transactions go into the file
        lines = ["Date,Description,Amount (EUR)"] + [
            f'{t["date"]},"{t["description"]}",{t["amount"]:.2f}' for t in rows
        ]
        return ("\n".join(lines) + "\n").encode()

    # disputes

    def disputes(self, sess: dict) -> dict:
        w = self.signed_in(sess)
        card_txns = sorted(
            (t for t in w["transactions"] if t["account"] == 3 and t["type"] in ("card", "refund")),
            key=lambda t: t["date"],
            reverse=True,
        )
        return {"disputes": sorted(w["disputes"], key=lambda d: d["opened"], reverse=True), "transactions": card_txns}

    def open_dispute(self, sess: dict, body: dict) -> dict:
        w = self.signed_in(sess)
        try:
            tid = int(body.get("transaction"))
        except (TypeError, ValueError):
            raise ApiError(400, "Choose the card payment.") from None
        t = next((t for t in w["transactions"] if t["id"] == tid and t["account"] == 3), None)
        if not t:
            raise ApiError(400, "Choose the card payment.")
        # BUG-29: payments older than 120 days can be disputed
        # BUG-30: the same payment can be disputed twice
        # BUG-31: refunds (money in) can be disputed
        reason = _text(body, "reason", 500)
        if not reason:
            raise ApiError(400, "Tell us what went wrong.")
        w["disputes"].append(
            {
                "id": w["next_id"],
                "transaction": t["id"],
                "description": t["description"],
                "amount": t["amount"],
                "date": t["date"],
                "reason": reason,
                "status": "open",
                "reply": "",
                "internal": "",
                "opened": w["today"],
            }
        )
        w["next_id"] += 1
        return self.disputes(sess)

    # settings

    def settings(self, sess: dict) -> dict:
        w = self.signed_in(sess)
        return w["settings"]

    def save_settings(self, sess: dict, body: dict) -> dict:
        w = self.signed_in(sess)
        threshold = body.get("alert_threshold")
        if isinstance(threshold, bool) or not isinstance(threshold, int | float) or not 0 <= threshold <= 100_000:
            raise ApiError(400, "Enter an alert amount.")
        email = _text(body, "email", 120)  # BUG-35: the address isn't checked
        if not email:
            raise ApiError(400, "Enter an email address.")
        w["settings"].update(alert_threshold=float(threshold), email=email, alerts=bool(body.get("alerts")))
        return w["settings"]

    def change_password(self, sess: dict, body: dict) -> dict:
        self.signed_in(sess)
        user = self.user(sess)
        current, new = body.get("current"), body.get("new")
        if not isinstance(current, str) or not hmac.compare_digest(
            user["hash"], data.password_hash(current, bytes.fromhex(user["salt"]))
        ):
            raise ApiError(400, "Your current password is wrong.")
        if not isinstance(new, str) or not new:  # BUG-32: the password rules aren't checked
            raise ApiError(400, "Enter a new password.")
        user["hash"] = data.password_hash(new, bytes.fromhex(user["salt"]))
        return {"ok": True}

    # staff

    def staff(self, sess: dict) -> dict:
        w = self.signed_in(sess, "staff")
        everyday = self.account(w, 1)
        return {
            "disputes": sorted(w["disputes"], key=lambda d: d["opened"], reverse=True),
            "customer": {
                "name": "Nora Ellis",
                "account": everyday["name"],
                "number": everyday["number"],
                "overdraft": everyday["overdraft"],
                "balance": self.balance(w, 1),
            },
        }

    def decide_dispute(self, sess: dict, did: int, body: dict) -> dict:
        w = self.signed_in(sess, "staff")
        d = next((d for d in w["disputes"] if d["id"] == did), None)
        if not d:
            raise ApiError(404, "We couldn't find that dispute.")
        if d["status"] != "open":
            raise ApiError(409, "That dispute is already closed.")
        action = body.get("action")
        reply, internal = _text(body, "reply", 500), _text(body, "internal", 500)
        if action == "refund":
            w["transactions"].append(
                {
                    "id": w["next_id"],
                    "account": 1,
                    "date": w["today"],
                    "description": f"Dispute refund – {d['description']}",
                    "amount": -d["amount"],
                    "type": "refund",
                    "status": "posted",
                    "reference": "",
                    "foreign": "",
                }
            )
            # BUG-36: the refund goes to the Everyday Account, not the card that was charged
            w["next_id"] += 1
            d.update(status="refunded", reply=reply or "We've refunded this payment.", internal=internal)
        elif action == "reject":
            if not reply:
                raise ApiError(400, "Write a reply for the customer.")
            d.update(status="rejected", reply=reply, internal=internal)
        else:
            raise ApiError(400, "Refund or reject.")
        return self.staff(sess)

    def set_overdraft(self, sess: dict, body: dict) -> dict:
        w = self.signed_in(sess, "staff")
        amount = body.get("amount")
        if isinstance(amount, bool) or not isinstance(amount, int | float) or amount < 0:
            raise ApiError(400, "Enter an overdraft limit.")
        # BUG-38: limits above €2,000 are accepted
        self.account(w, 1)["overdraft"] = money(amount)
        return self.staff(sess)


def render(path: str, store: Store, sess: dict, status_page: str | None = None) -> bytes:
    name, title, _ = PAGES[path] if not status_page else (status_page, "Page not found", None)
    if status_page == "403":
        title = "Not for this account"
    user = store.user(sess)
    if not user:
        nav = '<a href="/" data-nav="landing">Welcome</a><a href="/help" data-nav="help">Fees and limits</a>'
        account = '<a href="/login" id="login-link">Log in</a>'
    else:
        if user["role"] == "customer":
            links = [
                ("/accounts", "accounts", "Accounts"),
                ("/transfer", "transfer", "Move money"),
                ("/payees", "payees", "Payees"),
                ("/scheduled", "scheduled", "Scheduled"),
                ("/card", "card", "Card"),
                ("/statements", "statements", "Statements"),
                ("/disputes", "disputes", "Disputes"),
            ]
        else:
            links = [("/staff", "staff", "Staff desk")]
        nav = "".join(f'<a href="{h}" data-nav="{k}">{t}</a>' for h, k, t in links)
        nav += '<a href="/help" data-nav="help">Fees and limits</a>'
        first = html.escape(user["name"].split()[0])
        account = (
            f'<a href="/settings" class="who">{first}</a>'
            if user["role"] == "customer"
            else f'<span class="who">{first}</span>'
        )
        account += '<button type="button" id="logout" class="link">Log out</button>'
    script = f'<script src="/static/{name}.js" defer></script>' if (STATIC_DIR / f"{name}.js").exists() else ""
    out = (PAGES_DIR / "_layout.html").read_text()
    values = {
        "title": html.escape(title),
        "page": name,
        "role": user["role"] if user else "",
        "nav": nav,
        "account": account,
        "content": (PAGES_DIR / f"{name}.html").read_text(),
        "scripts": script,
    }
    for k, v in values.items():
        out = out.replace("{{" + k + "}}", v)
    return out.encode()


def make_handler(store: Store | None = None):
    store = store or Store()
    static = {f.name: f for f in STATIC_DIR.iterdir() if f.is_file() and f.suffix in STATIC_TYPES}

    class Handler(BaseHTTPRequestHandler):
        server_version = "copperleaf"

        def log_message(self, fmt, *args):
            pass

        def _session(self) -> tuple[str, dict, bool]:
            sid = None
            try:
                cookie = SimpleCookie(self.headers.get("Cookie", ""))
                sid = cookie["cl_sid"].value if "cl_sid" in cookie else None
            except CookieError:
                pass
            new_sid, sess = store.session(sid)
            return new_sid, sess, new_sid != sid

        def _send(self, status: int, body: bytes, ctype: str, extra: dict | None = None):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in {**SECURITY_HEADERS, **(extra or {})}.items():
                self.send_header(k, v)
            if self._new_sid:
                secure = "; Secure" if self.headers.get("X-Forwarded-Proto") == "https" else ""
                self.send_header("Set-Cookie", f"cl_sid={self._sid}; Path=/; HttpOnly; SameSite=Lax{secure}")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, status: int, payload: dict):
            self._send(status, json.dumps(payload).encode(), "application/json")

        def _body(self) -> dict:
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                raise ApiError(400, "Bad request.") from None
            if length > MAX_BODY:
                raise ApiError(413, "Request too large.")
            raw = self.rfile.read(length) if length > 0 else b""
            try:
                payload = json.loads(raw or b"{}")
            except ValueError:
                raise ApiError(400, "Send JSON.") from None
            if not isinstance(payload, dict):
                raise ApiError(400, "Send a JSON object.")
            return payload

        def do_HEAD(self):
            self._handle("GET")

        def do_GET(self):
            self._handle("GET")

        def do_POST(self):
            self._handle("POST")

        def _handle(self, method: str):
            self._sid, self._new_sid = None, False
            url = urlsplit(self.path)
            path = url.path.rstrip("/") or "/"
            query = parse_qs(url.query)
            try:
                if path == "/healthz":
                    return self._send(200, b"ok", "text/plain")
                if path == "/robots.txt":
                    return self._send(200, b"User-agent: *\nAllow: /\n", "text/plain")
                if path.startswith("/static/") and path[8:] in static:
                    f = static[path[8:]]
                    return self._send(200, f.read_bytes(), STATIC_TYPES[f.suffix])
                with store.lock:
                    self._sid, sess, self._new_sid = self._session()
                    if path.startswith("/api/"):
                        body = self._body() if method == "POST" else {}
                        result = self._api(sess, method, path, body, query)
                        if isinstance(result, bytes):
                            extra = {"Content-Disposition": 'attachment; filename="copperleaf.csv"'}
                            return self._send(200, result, "text/csv; charset=utf-8", extra)
                        return self._json(200, result)
                    if method != "GET":
                        return self._send(405, b"Method not allowed", "text/plain", {"Allow": "GET, HEAD"})
                    if path not in PAGES:
                        return self._send(404, render("/", store, sess, "404"), "text/html; charset=utf-8")
                    role = PAGES[path][2]
                    user = store.user(sess)
                    if role and not user:
                        location = "/login?next=" + quote(self.path, safe="")
                        return self._send(302, b"", "text/plain", {"Location": location})
                    if role and user["role"] != role:
                        return self._send(403, render("/", store, sess, "403"), "text/html; charset=utf-8")
                    return self._send(200, render(path, store, sess), "text/html; charset=utf-8")
            except ApiError as err:
                return self._json(err.status, {"ok": False, "error": str(err)})
            except Exception:
                return self._json(500, {"ok": False, "error": "Internal Server Error"})

        def _api(self, sess: dict, method: str, path: str, body: dict, query: dict):
            q = lambda k: (query.get(k) or [""])[0]  # noqa: E731
            if method == "GET":
                gets = {
                    "/api/me": lambda: store.me(sess),
                    "/api/overview": lambda: store.overview(sess),
                    "/api/payees": lambda: store.payees(sess),
                    "/api/scheduled": lambda: store.scheduled(sess),
                    "/api/card": lambda: store.card(sess),
                    "/api/statements": lambda: store.statement(sess, int(q("account") or 1), q("month")),
                    "/api/statements.csv": lambda: store.statement_csv(sess, int(q("account") or 1), q("month")),
                    "/api/disputes": lambda: store.disputes(sess),
                    "/api/settings": lambda: store.settings(sess),
                    "/api/staff": lambda: store.staff(sess),
                }
                if path in gets:
                    return gets[path]()
                routes = (
                    (r"/api/accounts/(\d+)/transactions", lambda i: store.transactions(sess, int(i), query)),
                    (r"/api/accounts/(\d+)\.csv", lambda i: store.transactions_csv(sess, int(i), query)),
                )
            else:
                posts = {
                    "/api/login": lambda: store.login(sess, body),
                    "/api/logout": lambda: sess.update(user=None) or {"ok": True},
                    "/api/transfers": lambda: store.transfer(sess, body),
                    "/api/payees": lambda: store.add_payee(sess, body),
                    "/api/card/freeze": lambda: store.freeze(sess, body),
                    "/api/card/settings": lambda: store.card_settings(sess, body),
                    "/api/disputes": lambda: store.open_dispute(sess, body),
                    "/api/settings": lambda: store.save_settings(sess, body),
                    "/api/password": lambda: store.change_password(sess, body),
                    "/api/staff/overdraft": lambda: store.set_overdraft(sess, body),
                }
                if path in posts:
                    return posts[path]()
                routes = (
                    (r"/api/payees/(\d+)/delete", lambda i: store.delete_payee(sess, int(i))),
                    (r"/api/scheduled/(\d+)/cancel", lambda i: store.cancel_scheduled(sess, int(i))),
                    (r"/api/staff/disputes/(\d+)", lambda i: store.decide_dispute(sess, int(i), body)),
                )
            for pattern, run in routes:
                m = re.fullmatch(pattern, path)
                if m:
                    return run(m.group(1))
            raise ApiError(404, "Not found.")

    return Handler


def serve(env: dict[str, str] | None = None) -> None:
    env = dict(os.environ if env is None else env)
    port = int(env.get("PORT", "8085"))
    httpd = ThreadingHTTPServer(("0.0.0.0", port), make_handler())
    print(f"Copperleaf Bank listening on :{port}", flush=True)
    httpd.serve_forever()
