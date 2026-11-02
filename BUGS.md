# Copperleaf Bank: answer key (40 planted bugs)

Copperleaf Bank is a demo online bank (accounts and transactions, transfers, payees, scheduled payments, a credit
card, statements, card disputes, settings, and a staff desk) with **functional bugs planted on purpose**, for
checking what the AI QA Scanner finds. Most bugs break a rule published on the site, so finding them takes the
rules, some arithmetic, a download, a second page or the staff account.

This file is never served, and nothing the site serves (pages, scripts, CSS, images) names or hints at a bug.
Server-side code marks each one with a `BUG-nn` comment; `tests/test_copperleaf.py` keeps the server-side ones in
place. The rules every bug breaks are published on the site's **Fees and limits** page (`/help`).

## Run it

- **Locally**: `python -m copperleaf` (port 8085, or `PORT`), then open http://localhost:8085.
- **Railway**: New service → GitHub repo → this repository, then **Generate domain**. `railway.json` sets the start
  command and health check; no variables or volume needed.

Every visitor (cookie) gets a private copy of the demo world, dated around today, so parallel scans never see each
other's changes. Logging in as Nora and then Omar in the same browser shares one world, so what Omar does shows up
for Nora. A restart resets everything.

## Test data

Days below are counted from the day the session starts ("day 0" is today, UTC).

| What | Value |
|---|---|
| Accounts (password `Copperleaf@2026`, listed on the login page) | `nora@copperleaf.test` Nora Ellis, customer · `omar@copperleaf.test` Omar Haddad, bank staff (disputes and overdrafts) |
| Everyday Account | Balance €1,240.35, arranged overdraft €500, two pending card payments (Uber €18.40, Shell €45.80): available should be €1,676.15. Salary €2,850 on the 25th, rent €950 on the 1st, groceries (TESCO STORES 2231, Tesco Express, LIDL 118), gym €35 on the 15th |
| Rainy Day Saver | €8,500.00 at 3.0%; €200 in and interest on the last day of each month; already 3 withdrawals this month |
| Copper Card | Owes €742.18, credit limit €2,000, last statement €690.00, expires 08/2028. Purchases include AMAZON.COM (USD 50.00 → €46.00, day −6), ZARA ONLINE €89.95 and its €29.95 refund, NETFLIX.COM €12.99 monthly, RYANAIR €142.30 (day −140) |
| Correct total balance | €1,240.35 + €8,500.00 − €742.18 = €8,998.17 |
| Payees | Landlord P. Hart (GB82 WEST 1234 5698 7654 32), Mum – Ruth Ellis (IE29 …), FitLab Gyms (NL91 …) |
| Scheduled payments | Rent €950 monthly on the 1st · €200 to savings monthly on the **31st** · FitLab €35 monthly on the 15th · €120 to Mum on day +5 (ref BIRTHDAY) · €300 to Mum on day +9, **cancelled** |
| Disputes | ZARA ONLINE: rejected, with a staff reply and a staff-only internal note · NETFLIX.COM: open |

Difficulty: **Medium** needs a flow or a comparison; **Hard** needs the published rules, a second page, a download,
a reload or the staff account; **Expert** needs arithmetic across several numbers, a checksum, or a calendar edge.

## The bugs

### Accounts and transactions

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-01 | Total balance adds the card debt | Accounts: Total balance | €8,998.17 (holdings minus card debt) | €10,482.53: the €742.18 owed is added | High | Hard | `static/accounts.js` (`Math.abs`) |
| BUG-02 | Available ignores pending payments | Accounts / Everyday Account: Available | €1,676.15 (balance + overdraft − €64.20 pending) | €1,740.35 | High | Hard | `server.py` `Store.summary` |
| BUG-03 | Search is case-sensitive | Everyday Account: search "tesco" | The Tesco payments | "0 transactions" ("TESCO" finds them) | Low | Medium | `server.py` `Store.transactions` |
| BUG-04 | The "To" date is left out | From and To both set to a day with transactions | That day's transactions | "0 transactions" | Medium | Medium | `server.py` `Store.transactions` |
| BUG-05 | Money in / out cover only the page | Everyday Account, no filters | Totals for every matching transaction | "Money in €300.00": just the 10 rows shown | Medium | Hard | `static/account.js` (ignores the server's totals) |
| BUG-06 | CSV download drops the minus sign | Download CSV | `-42.18` for card payments | `42.18`: money out looks like money in | Medium | Hard | `server.py` `Store.transactions_csv` |
| BUG-07 | "Largest amount first" sorts as text | Sort by Largest amount first | €2,850.00 salary first | €950.00 rent first (99 > 2850 as text) | Low | Hard | `server.py` `Store.transactions` |

### Moving money

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-08 | More than two decimals accepted | Move money, amount `10.005` | "Enter an amount in euros and cents" | Review shows "€10.005"; sent | Medium | Medium | `server.py` `_amount`, `static/transfer.js` |
| BUG-09 | The €5,000 daily payee limit is per payment | Pay Mum €4,000, then €3,000 the same day | The second payment refused | Both sent (€7,000 in a day) | High | Hard | `server.py` `Store.transfer` |
| BUG-10 | New payees have no €1,000 limit | Add a payee, pay them €1,500 straight away | Refused for 24 hours | Sent | High | Hard | `server.py` `Store.transfer` |
| BUG-11 | No fee on the 4th savings withdrawal | Rainy Day Saver → Everyday, €50 (3 withdrawals already this month) | A €2 fee | No fee | Medium | Hard | `server.py` `Store.transfer` |
| BUG-12 | Savings can go below zero | Rainy Day Saver → Everyday, €9,000 | Refused (no overdraft on savings) | Sent; savings balance negative | Critical | Medium | `server.py` `Store.transfer` |
| BUG-13 | Weekend payments keep the weekend date | Pay someone on a future Saturday | Leaves on the Monday | "Leaves your account on Sat …" | Medium | Hard | `server.py` `Store.transfer` |
| BUG-14 | An account can pay itself | From Everyday Account to Everyday Account | Refused | Sent | Low | Medium | `server.py` `Store.transfer`, `static/transfer.js` |
| BUG-15 | Long references are cut without warning | Reference "Holiday deposit for Lisbon" (form allows 35) | Refused or limited to 18 in the form | Review shows it whole; saved as "Holiday deposit fo" | Low | Medium | `server.py` `Store.transfer`, `pages/transfer.html` (`maxlength="35"`) |

### Payees and scheduled payments

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-16 | IBAN check digits aren't checked | Add a payee with `DE89 3704 0044 0532 0130 01` (…00 is the valid one) | "That IBAN isn't valid" | Added | High | Expert | `server.py` `iban_ok` |
| BUG-17 | The same IBAN can be saved twice | Add a payee with Landlord P. Hart's IBAN | Refused | Added | Low | Medium | `server.py` `Store.add_payee` |
| BUG-18 | Deleting a payee leaves their payments running | Delete FitLab Gyms, open Scheduled | FitLab's monthly €35 cancelled | Still active | High | Hard | `server.py` `Store.delete_payee` |
| BUG-19 | Payments on the 31st skip short months | Scheduled: €200 to savings, monthly on day 31 | Paid on the last day of shorter months | Next payments jump a month (e.g. 31 Dec, 31 Jan, 31 Mar) | High | Expert | `server.py` `upcoming` |
| BUG-20 | Cancel cancels a different payment | Scheduled: Cancel on the €120 to Mum (dialog names it), confirm | The €120 to Mum cancelled | Another payment (the €950 rent) cancelled | Critical | Hard | `static/scheduled.js` (index into the unsorted list) |
| BUG-21 | "Due in the next 30 days" counts cancelled payments | Scheduled: the total | Active payments only | Includes the cancelled €300 to Mum | Medium | Medium | `server.py` `Store.scheduled` |

### Card

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-22 | Saving card settings unfreezes the card | Freeze card, then Save settings | Card stays frozen | "Your card is active." | Critical | Hard | `server.py` `Store.card_settings` |
| BUG-23 | Monthly limit outside €50–€2,000 accepted | Limit 5000 (or 1), Save | Refused | "Settings saved." | Medium | Medium | `server.py` `Store.card_settings` |
| BUG-24 | Minimum payment uses the credit limit | Card: Minimum payment | €25.00 (3% of €690 is €20.70) | €60.00 (3% of €2,000) | High | Expert | `server.py` `Store.card` |
| BUG-25 | Expiry month is one early | Card picture | Expires 08/28 | 07/28 | Low | Hard | `static/card.js` (`getUTCMonth`) |
| BUG-40 | No non-euro fee on foreign payments | Copper Card transactions: AMAZON.COM (USD 50.00) | €46.00 plus a €1.27 (2.75%) fee line | €46.00, no fee | Medium | Expert | `data.py` / card posting (fee never added) |

### Statements

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-26 | Savings statements don't add up | Statements: Rainy Day Saver, last month | Opening + in − out = closing | Interest is left out of Money in, so the sum is about €20 short of Closing | Medium | Expert | `server.py` `Store.statement` |
| BUG-27 | A statement includes the 1st of the next month | Statements: Everyday Account, last month | The 1st to the last day | Lists the rent from the 1st of this month; this month then opens at a different balance than last month closed | Medium | Hard | `server.py` `Store.statement` |
| BUG-28 | Statement CSV has every account's transactions | Rainy Day Saver statement, Download CSV | Savings transactions only | Includes TESCO, NETFLIX and other accounts' rows | High | Hard | `server.py` `Store.statement_csv` |

### Disputes

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-29 | Payments older than 120 days can be disputed | Dispute RYANAIR (day −140) | Refused | "Dispute opened" | Medium | Hard | `server.py` `Store.open_dispute` |
| BUG-30 | The same payment can be disputed twice | Dispute NETFLIX.COM (already open) | Refused | Opened again | Low | Medium | `server.py` `Store.open_dispute` |
| BUG-31 | Refunds can be disputed | Dispute "ZARA ONLINE refund" (+€29.95) | Not listed / refused | Opened | Low | Medium | `server.py` `Store.open_dispute` |
| BUG-37 | Staff-only notes are shown to the customer | Disputes: the rejected ZARA ONLINE dispute | Only Copperleaf's reply | Also "Customer has filed 3 disputes this year. Flag for review…" | High | Hard | `server.py` `Store.disputes` (sends it), `static/disputes.js` (shows it) |

### Security and settings

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-32 | Password rules aren't enforced | Settings: change password to `abc` | Refused (10+ characters with a number) | "Password changed." | High | Medium | `server.py` `Store.change_password` |
| BUG-33 | Alert amount loses its cents | Alert amount 50.50, Save | €50.50 | "…drops below €50.00" | Low | Hard | `static/settings.js` (`parseInt`) |
| BUG-34 | No lockout after 5 wrong passwords | Log in wrongly 6 times, then correctly | Locked for 15 minutes | Logged in | Critical | Hard | `server.py` `Store.login` |
| BUG-35 | Alert email isn't validated | Send alerts to `nora@`, Save | Refused | "Saved. We'll email nora@…" | Medium | Medium | `server.py` `Store.save_settings` |

### Staff desk (Omar)

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-36 | Dispute refunds go to the wrong account | As Omar, Refund the NETFLIX.COM dispute; as Nora, check the accounts | +€12.99 on the Copper Card | +€12.99 on the Everyday Account; the card still owes it | High | Hard | `server.py` `Store.decide_dispute` |
| BUG-38 | Overdrafts above €2,000 accepted | As Omar, set Nora's overdraft to 5000 | Refused | "Overdraft set to €5,000.00" | High | Medium | `server.py` `Store.set_overdraft` |

### Errors

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-39 | An unknown account hangs on "Loading…" | Open `/account?id=99` | "We couldn't find that account" | "Loading…" forever and a JavaScript error | Low | Medium | `static/account.js` (no check on the response) |

## What is not a planted bug

- Console errors that come with a bug or a page: 401 on wrong passwords, 404 and the JavaScript error on an unknown
  account (BUG-39), 403 on `/staff` as Nora, 404 on unknown pages.
- Bugs that combine: BUG-27 also shifts last month's closing balance; BUG-08 shows "€10.00" after sending €10.005.
- Date pickers show dates in the browser's format.
- Each visitor has a private world: changes in one browser session do not show in another.
- "Demo bank for QA testing" in the footer and the demo accounts on the login page.

By area: accounts and transactions 7, moving money 8, payees and scheduled payments 6, card 5, statements 3,
disputes 4, security and settings 4, staff desk 2, errors 1.
By difficulty: Medium 15, Hard 20, Expert 5. By severity: Critical 4, High 13, Medium 13, Low 10.
