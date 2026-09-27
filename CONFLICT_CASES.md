# NimbusRetail — Deliberate Conflict / Ambiguity Cases (10)

These are intentional contradictions woven into the document set, for testing
`contradiction_detector.py` and `config/policy_precedence.py`.

| # | Document A | Document B | Conflict |
|---|---|---|---|
| 1 | SOP-07 §4.2 (Escalation Procedure) | FAQ-02 Q1 | SOP says escalate refunds above PKR 10,000 to Team Leader; FAQ says escalate above PKR 5,000 to Branch Manager |
| 2 | DOC-04 §1 (Commission Structure) | FAQ-03 Q1 | Commission policy implies standard pricing; FAQ allows up to 15% discount without approval, changing the effective deal value commission is calculated on |
| 3 | DOC-02 §1 (Annual Leave) | DOC-01-OLD (Employee Handbook, old) | Leave Policy says 18 days annual leave; older Handbook text implied a different (15-day, pre-v2) entitlement — tests version precedence |
| 4 | DOC-06 §2 (Submission Timeline) | DOC-16 §3 (Reimbursement to Vendors) | Expense claims must be submitted within 7 days; vendor invoices are paid within 15 days — different SLAs that could be conflated by a generic "reimbursement" query |
| 5 | DOC-07 §2 (Incident Reporting) | DOC-10 §2 (Incident Escalation) | Warehouse SOP requires incident logging within 24 hours; Branch Manager Compliance Manual allows review within 72 hours — ambiguous which SLA governs |
| 6 | DOC-09 §2 (Critical Ticket Response) | DOC-03 (Information Security Policy) | IT SOP sets 1-hour response for critical tickets; Security Policy's incident-response expectations for security-related tickets are not explicitly reconciled with this |
| 7 | DOC-13 §2 (Dress Code) | DOC-08 §2 (Tone of Voice) | Code of Conduct mandates business-formal attire; Marketing's brand voice guide implies a casual, approachable culture — ambiguous, not a hard numeric conflict |
| 8 | DOC-14 §1 (Remote Work Eligibility) | DOC-01-OLD (Employee Handbook, old) | New Remote Work Policy allows remote work without VP approval; the superseded Handbook text required VP approval — resolved by version precedence (latest policy wins) |
| 9 | DOC-11 §2 (Data Retention) | DOC-15 §2 (Data Retention) | Analytics SOP retains raw data for 1 year; Data Privacy Policy allows customer data retention up to 3 years — different retention windows for overlapping data |
| 10 | DOC-12 §1 (Review Cadence) | DOC-10 §3 (Annual Performance Review) | Team Leader process requires quarterly agent reviews; Branch Manager Compliance Manual only mandates annual reviews — different cadence for similar review obligations |

**Expected precedence** (per `config/policy_precedence.py`): Latest Approved Policy > Department SOP > FAQ > Informal Guidance. Cases #1, #3, #8 are the clearest tests of this rule; the rest are cross-document ambiguities a reviewer should be routed to check manually.
