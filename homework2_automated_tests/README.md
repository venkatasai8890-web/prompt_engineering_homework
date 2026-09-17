# Homework 2 — Automated Test Scripts (OSCS)

Automated `pytest` tests for the Outpatient Patient Scheduling & Care System
(OSCS), extending the manual test cases in
[`../homework2/01_test_cases.md`](../homework2/01_test_cases.md) into
executable scripts.

## What this is (and isn't)

There is no real OSCS backend to test against, so this suite ships a small
**mock / reference implementation**, [`mock_oscs_api.py`](mock_oscs_api.py),
that models the business rules described in the PRD
(`ABC_Health_Care_Outpatient_Scheduling_PRD.pdf`) and in
[`../homework2/03_api_specifications.md`](../homework2/03_api_specifications.md):
appointment lifecycle states, policy-window checks for reschedule/cancel,
waitlist offer/expiry, overbooking with justification, RBAC permission
checks, and audit logging.

**All data used by the tests is synthetic and fabricated** (see
`conftest.py`) — fake emails like `synthetic.patient001@example-test.invalid`,
fake phone numbers, fake provider/location IDs. **No real patient
information or PHI is used anywhere in this suite.**

## Files

| File | Purpose |
|---|---|
| `mock_oscs_api.py` | In-memory reference implementation of OSCS business logic (not production code). |
| `conftest.py` | Shared pytest fixtures: fresh system instance, synthetic patients/providers/visit types/slots, RBAC users. |
| `test_scheduling.py` | Automated test cases, grouped by area, each referencing its source Test Case ID from `01_test_cases.md`. |
| `README.md` | This file. |

## Coverage

The suite covers, per the instructor's requirement, representative scenarios for:

- Patient registration & OTP verification, login rate limiting (FR-001)
- Profile management (FR-002)
- Appointment self-scheduling: instant booking, request-and-approve, double-booking conflict, referral/new-patient eligibility constraints (FR-003, FR-107)
- Provider availability search and resource-conflict prevention (FR-101, FR-102, FR-104)
- Reschedule and cancellation within/outside policy windows (FR-004)
- Waitlist offer generation, expiry, and acceptance (FR-105)
- Overbooking with/without justification and policy gating (FR-106)
- Appointment lifecycle state transitions, valid and invalid (FR-108)
- Front-desk and mobile self check-in, including time-window/geo-fence denial (FR-202, FR-203)
- Care plan creation, task status updates, overdue escalation, "schedule next" (FR-301–303)
- Notification delivery and opt-out suppression, inbound keyword routing (FR-401, FR-402)
- RBAC / authorization: role-restricted report export, audit log access, PHI access; audit entries for actor/timestamp/before-after (Section 2 & 7 NFRs, FR-503, FR-603)

## Requirements

- Python 3.9+
- `pytest`

## Install

From this directory (or the repo root — paths below assume you run pytest
from inside `homework2_automated_tests/`):

```bash
python3 -m venv .venv        # optional, if you want an isolated environment
source .venv/bin/activate    # optional
pip install pytest
```

## Run the tests

```bash
cd homework2_automated_tests
pytest -v
```

To run a single test class or test:

```bash
pytest -v test_scheduling.py::TestWaitlist
pytest -v test_scheduling.py::TestWaitlist::test_waitlist_offer_expires_and_releases_slot
```

To get a short pass/fail summary line at the end:

```bash
pytest -q
```

## Notes

- Tests use a fixed, injected reference time (`now` fixture in
  `conftest.py`) rather than the real wall clock, so results are
  deterministic and don't depend on when you run them.
- Jenkins / ALM integration is intentionally **not** included (optional,
  out of scope per the assignment).
