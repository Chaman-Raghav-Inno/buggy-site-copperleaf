"""Copperleaf Bank's demo world: accounts, transactions, payees, standing orders, cards and disputes, dated from today.

Every visitor gets a fresh copy (see server.Store), so scans never disturb each other.
"""

import datetime as dt
import hashlib

PASSWORD = "Copperleaf@2026"
SALT = b"copperleaf-demo-salt"

DAILY_PAYEE_LIMIT = 5000.0
NEW_PAYEE_LIMIT = 1000.0
FREE_SAVINGS_WITHDRAWALS = 3
SAVINGS_FEE = 2.0
OVERDRAFT_MAX = 2000.0
CARD_LIMIT_RANGE = (50.0, 2000.0)
CREDIT_LIMIT = 2000.0
MIN_PAYMENT_RATE, MIN_PAYMENT_FLOOR = 0.03, 25.0
FOREIGN_FEE = 0.0275
DISPUTE_DAYS = 120
REFERENCE_MAX = 18
LOCKOUT_ATTEMPTS = 5
RATES = {"USD": 0.92, "GBP": 1.17}


def password_hash(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 20_000).hex()


DEMO_HASH = password_hash(PASSWORD, SALT)


def month_start(day: dt.date, back: int = 0) -> dt.date:
    y, m = divmod(day.year * 12 + day.month - 1 - back, 12)
    return dt.date(y, m + 1, 1)


def month_end(day: dt.date) -> dt.date:
    return month_start(day, -1) - dt.timedelta(days=1)


def world(today: dt.date) -> dict:
    """A fresh copy of everything one visitor can see and change."""
    txns: list[dict] = []

    def add(account, day, description, amount, kind, status="posted", **extra):
        row = {"id": len(txns) + 1, "account": account, "date": day.isoformat(), "description": description,
               "amount": round(amount, 2), "type": kind, "status": status, "reference": "", "foreign": ""}  # fmt: skip
        txns.append(row | extra)

    start = today - dt.timedelta(days=150)
    day = start
    shop = 0
    while day < today:
        if day.day == 25:
            add(1, day, "Salary – Brightwater Ltd", 2850.00, "salary")
        if day.day == 1:
            add(1, day, "Standing order – Landlord P. Hart", -950.00, "standing", reference="RENT FLAT 2")
        if day.day == 15:
            add(1, day, "FITLAB GYMS", -35.00, "standing", reference="MEMBER 20419")
        if day == month_end(day):
            add(1, day, "To Rainy Day Saver", -200.00, "transfer", reference="SAVINGS")
            add(2, day, "From Everyday Account", 200.00, "transfer", reference="SAVINGS")
            add(2, day, "Interest", round(8300 * 0.03 / 12, 2), "interest")
            add(3, day, "Payment – thank you", 500.00, "payment")
            add(1, day, "Copper Card payment", -500.00, "transfer")
        if (day - start).days % 4 == 0:
            shop += 1
            name = ("TESCO STORES 2231", "Tesco Express", "LIDL 118", "Corner Coffee")[shop % 4]
            add(1, day, name, -[42.18, 18.40, 63.75, 4.50][shop % 4], "card")
        if (day - start).days % 30 == 9:
            add(3, day, "NETFLIX.COM", -12.99, "card")
        day += dt.timedelta(days=1)

    add(1, today - dt.timedelta(days=33), "ASOS refund", 39.99, "refund")
    add(3, today - dt.timedelta(days=140), "RYANAIR", -142.30, "card")
    add(3, today - dt.timedelta(days=24), "ZARA ONLINE", -89.95, "card")
    add(3, today - dt.timedelta(days=20), "ZARA ONLINE refund", 29.95, "refund")
    add(3, today - dt.timedelta(days=6), "AMAZON.COM", -46.00, "card", foreign="USD 50.00")  # BUG-40: no 2.75% fee line
    add(3, today - dt.timedelta(days=3), "Apple Store", -219.00, "card")
    this_month = month_start(today)
    for i in range(3):
        when = max(this_month, today - dt.timedelta(days=1 - min(i, 1)))
        add(2, when, "To Everyday Account", -100.00, "transfer", reference="TOP UP")
        add(1, when, "From Rainy Day Saver", 100.00, "transfer", reference="TOP UP")
    add(1, today, "UBER *TRIP", -18.40, "card", status="pending")
    add(1, today - dt.timedelta(days=1), "SHELL 0412", -45.80, "card", status="pending")

    targets = {1: 1240.35, 2: 8500.00, 3: -742.18}
    for account, target in targets.items():
        posted = sum(t["amount"] for t in txns if t["account"] == account and t["status"] == "posted")
        add(account, start - dt.timedelta(days=1), "Opening balance", target - posted, "opening")

    def stamp(days: float) -> str:
        return (dt.datetime.combine(today, dt.time(9, 0)) + dt.timedelta(days=days)).isoformat()

    def next_day(day_of_month: int) -> str:
        d = today + dt.timedelta(days=1)
        while d.day != day_of_month:
            d += dt.timedelta(days=1)
        return d.isoformat()

    zara = next(t for t in txns if t["description"] == "ZARA ONLINE")
    netflix = max((t for t in txns if t["description"] == "NETFLIX.COM"), key=lambda t: t["date"])
    return {
        "today": today.isoformat(),
        "users": [
            {"id": 1, "name": "Nora Ellis", "email": "nora@copperleaf.test", "role": "customer", "salt": SALT.hex(),
             "hash": DEMO_HASH, "failed": 0},
            {"id": 2, "name": "Omar Haddad", "email": "omar@copperleaf.test", "role": "staff", "salt": SALT.hex(),
             "hash": DEMO_HASH, "failed": 0},
        ],
        "accounts": [
            {"id": 1, "name": "Everyday Account", "type": "everyday", "number": "40-21-77 41035522",
             "overdraft": 500.0},
            {"id": 2, "name": "Rainy Day Saver", "type": "savings", "number": "40-21-77 88310467", "overdraft": 0.0,
             "rate": 3.0},
            {"id": 3, "name": "Copper Card", "type": "card", "number": "•••• 4821", "overdraft": 0.0,
             "credit_limit": CREDIT_LIMIT, "statement_balance": 690.00,
             "due": (month_start(today, -1) + dt.timedelta(days=14)).isoformat()},
        ],
        "transactions": txns,
        "payees": [
            {"id": 1, "name": "Landlord P. Hart", "iban": "GB82 WEST 1234 5698 7654 32", "reference": "RENT FLAT 2",
             "created": stamp(-200)},
            {"id": 2, "name": "Mum – Ruth Ellis", "iban": "IE29 AIBK 9311 5212 3456 78", "reference": "FROM NORA",
             "created": stamp(-180)},
            {"id": 3, "name": "FitLab Gyms", "iban": "NL91 ABNA 0417 1643 00", "reference": "MEMBER 20419",
             "created": stamp(-160)},
        ],
        "scheduled": [
            {"id": 1, "from": 1, "to": "payee:1", "to_name": "Landlord P. Hart", "amount": 950.00, "repeat": "monthly",
             "day": 1, "next": next_day(1), "reference": "RENT FLAT 2", "status": "active"},
            {"id": 2, "from": 1, "to": "account:2", "to_name": "Rainy Day Saver", "amount": 200.00,
             "repeat": "monthly", "day": 31, "next": None, "reference": "SAVINGS", "status": "active"},
            {"id": 3, "from": 1, "to": "payee:3", "to_name": "FitLab Gyms", "amount": 35.00, "repeat": "monthly",
             "day": 15, "next": next_day(15), "reference": "MEMBER 20419", "status": "active"},
            {"id": 4, "from": 1, "to": "payee:2", "to_name": "Mum – Ruth Ellis", "amount": 120.00, "repeat": "once",
             "day": None, "next": (today + dt.timedelta(days=5)).isoformat(), "reference": "BIRTHDAY",
             "status": "active"},
            {"id": 5, "from": 1, "to": "payee:2", "to_name": "Mum – Ruth Ellis", "amount": 300.00, "repeat": "once",
             "day": None, "next": (today + dt.timedelta(days=9)).isoformat(), "reference": "FLIGHTS",
             "status": "cancelled"},
        ],
        "card": {"name": "Copper Card", "last4": "4821", "expiry": "2028-08", "frozen": False, "online": True,
                 "limit": 1500.0, "holder": "NORA ELLIS"},
        "disputes": [
            {"id": 1, "transaction": zara["id"], "description": zara["description"], "amount": zara["amount"],
             "date": zara["date"], "reason": "Parcel never arrived.", "status": "rejected",
             "reply": "The merchant sent proof of delivery to your address.",
             "internal": "Customer has filed 3 disputes this year. Flag for review if another one comes in.",
             "opened": (today - dt.timedelta(days=18)).isoformat()},
            {"id": 2, "transaction": netflix["id"], "description": netflix["description"], "amount": netflix["amount"],
             "date": netflix["date"], "reason": "I cancelled this subscription last month.", "status": "open",
             "reply": "", "internal": "", "opened": (today - dt.timedelta(days=2)).isoformat()},
        ],
        "settings": {"alert_threshold": 100.0, "email": "nora@copperleaf.test", "alerts": True},
        "next_id": 1000,
    }  # fmt: skip
