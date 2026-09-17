"""
Shared pytest fixtures providing a fresh mock OSCS system plus synthetic
(fabricated) test data for each test.

IMPORTANT: All patient/provider/contact data below is synthetic and made up
for testing purposes only. Nothing here is real PHI or a real person.
"""

from datetime import datetime, timedelta

import pytest

from mock_oscs_api import OSCSSystem, User


# ---------------------------------------------------------------------------
# Fixed reference "now" so tests are deterministic regardless of wall clock.
# ---------------------------------------------------------------------------

@pytest.fixture
def now():
    return datetime(2026, 1, 1, 8, 0, 0)


@pytest.fixture
def system():
    """A brand-new, empty in-memory OSCS system for each test."""
    return OSCSSystem()


# ---------------------------------------------------------------------------
# Synthetic RBAC users -- one per role referenced in the PRD / user stories.
# ---------------------------------------------------------------------------

@pytest.fixture
def front_desk_user():
    return User(user_id="staff_frontdesk_001", role="front_desk")


@pytest.fixture
def clinician_user():
    return User(user_id="staff_clinician_001", role="clinician")


@pytest.fixture
def nurse_user():
    return User(user_id="staff_nurse_001", role="nurse_care_coordinator")


@pytest.fixture
def clinic_manager_user():
    return User(user_id="staff_manager_001", role="clinic_manager")


@pytest.fixture
def system_admin_user():
    return User(user_id="staff_admin_001", role="system_admin")


@pytest.fixture
def billing_user():
    return User(user_id="staff_billing_001", role="billing_staff")


@pytest.fixture
def patient_role_user():
    """A patient acting as themselves -- lacks all staff permissions."""
    return User(user_id="pat_self_001", role="patient")


# ---------------------------------------------------------------------------
# Synthetic patients
# ---------------------------------------------------------------------------

@pytest.fixture
def synthetic_patient(system, now):
    """A freshly registered + OTP-verified synthetic patient."""
    patient = system.register_patient(
        email="synthetic.patient001@example-test.invalid",
        phone="+15550000001",
        otp="111111",
        now=now,
    )
    system.verify_otp(patient.patient_id, "111111", now=now)
    return patient


@pytest.fixture
def synthetic_new_patient(system, now):
    """A synthetic patient flagged as a brand-new patient (never seen before)."""
    patient = system.register_patient(
        email="synthetic.newpatient002@example-test.invalid",
        phone="+15550000002",
        otp="222222",
        now=now,
    )
    system.verify_otp(patient.patient_id, "222222", now=now)
    patient.is_new_patient = True
    return patient


@pytest.fixture
def synthetic_established_patient_with_referral(system, now, referral_visit_type):
    patient = system.register_patient(
        email="synthetic.established003@example-test.invalid",
        phone="+15550000003",
        otp="333333",
        now=now,
    )
    system.verify_otp(patient.patient_id, "333333", now=now)
    patient.is_new_patient = False
    patient.referrals.add(referral_visit_type.visit_type_id)
    return patient


# ---------------------------------------------------------------------------
# Synthetic providers / locations (plain string identifiers -- FR-101/FR-102)
# ---------------------------------------------------------------------------

@pytest.fixture
def synthetic_provider_id():
    return "prov_synthetic_01"


@pytest.fixture
def synthetic_second_provider_id():
    return "prov_synthetic_02"


@pytest.fixture
def synthetic_location_id():
    return "loc_synthetic_01"


# ---------------------------------------------------------------------------
# Synthetic visit types (FR-103, FR-106, FR-107)
# ---------------------------------------------------------------------------

@pytest.fixture
def standard_visit_type(system):
    """Instant-booking, no special constraints, standard policy window."""
    return system.add_visit_type(
        name="Standard Follow-up",
        duration_minutes=30,
        instant_booking=True,
        requires_referral=False,
        new_patients_allowed=True,
        overbooking_allowed=False,
        reschedule_cancel_window_hours=24,
    )


@pytest.fixture
def referral_visit_type(system):
    """Requires a referral on file to book (FR-107)."""
    return system.add_visit_type(
        name="Specialist Consult",
        duration_minutes=45,
        instant_booking=True,
        requires_referral=True,
        new_patients_allowed=True,
        overbooking_allowed=False,
        reschedule_cancel_window_hours=48,
    )


@pytest.fixture
def established_patients_only_visit_type(system):
    """Restricted to established patients only (FR-107)."""
    return system.add_visit_type(
        name="Established Patient Physical",
        duration_minutes=30,
        instant_booking=True,
        requires_referral=False,
        new_patients_allowed=False,
        reschedule_cancel_window_hours=24,
    )


@pytest.fixture
def overbookable_visit_type(system):
    """Overbooking permitted for this visit type (FR-106)."""
    return system.add_visit_type(
        name="Urgent Same-Day",
        duration_minutes=15,
        instant_booking=True,
        requires_referral=False,
        new_patients_allowed=True,
        overbooking_allowed=True,
        reschedule_cancel_window_hours=2,
    )


@pytest.fixture
def request_and_approve_visit_type(system):
    """Not instant-booking -- goes to REQUESTED state (FR-003/FR-108)."""
    return system.add_visit_type(
        name="New Patient Intake",
        duration_minutes=60,
        instant_booking=False,
        requires_referral=False,
        new_patients_allowed=True,
        reschedule_cancel_window_hours=24,
    )


# ---------------------------------------------------------------------------
# Synthetic slots
# ---------------------------------------------------------------------------

@pytest.fixture
def make_slot(system, synthetic_provider_id, synthetic_location_id, now):
    """Factory fixture: make_slot(visit_type, hours_from_now=72) -> Slot"""

    def _make(visit_type, hours_from_now=72, provider_id=None, location_id=None):
        return system.add_slot(
            provider_id=provider_id or synthetic_provider_id,
            location_id=location_id or synthetic_location_id,
            start_time=now + timedelta(hours=hours_from_now),
            visit_type_id=visit_type.visit_type_id,
        )

    return _make
