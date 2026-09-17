"""
Mock / reference implementation of the Outpatient Patient Scheduling & Care
System (OSCS) described in ABC_Health_Care_Outpatient_Scheduling_PRD.pdf.

This is NOT the production system. It is a small, self-contained, in-memory
stand-in that implements just enough business logic (state machines, policy
windows, RBAC checks, audit logging) to exercise the behaviors captured in
homework2/01_test_cases.md, 02_user_stories.md and 03_api_specifications.md
against synthetic data.

No real patient information / PHI is used anywhere in this module or its
tests -- all data is fabricated by the test fixtures in conftest.py.
"""

from __future__ import annotations

import itertools
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set


# ---------------------------------------------------------------------------
# Errors (map conceptually to HTTP status codes used in 03_api_specifications.md)
# ---------------------------------------------------------------------------

class OSCSError(Exception):
    """Base error for all mock-API failures."""


class ValidationError(OSCSError):
    """Maps to 400 Bad Request."""


class ForbiddenError(OSCSError):
    """Maps to 403 Forbidden (RBAC / policy-window denial)."""


class NotFoundError(OSCSError):
    """Maps to 404 Not Found."""


class ConflictError(OSCSError):
    """Maps to 409 Conflict (double-booking, resource conflict)."""


class UnprocessableError(OSCSError):
    """Maps to 422 Unprocessable Entity (eligibility constraint failed)."""


class ExpiredError(OSCSError):
    """Maps to 410 Gone (expired OTP / waitlist offer)."""


class RateLimitedError(OSCSError):
    """Maps to 429 Too Many Requests."""


# ---------------------------------------------------------------------------
# RBAC roles / permissions -- Section 2 and Section 7 (NFR security) of PRD
# ---------------------------------------------------------------------------

ROLE_PERMISSIONS: Dict[str, Set[str]] = {
    "patient": {"self_service"},
    "front_desk": {"manage_scheduling", "check_in", "view_intake_status"},
    "clinician": {"manage_scheduling", "manage_care_plan", "view_patient_phi"},
    "nurse_care_coordinator": {"manage_care_plan", "manage_tasks", "view_patient_phi"},
    "clinic_manager": {"manage_scheduling", "manage_overbooking_policy", "view_reports"},
    "system_admin": {
        "manage_scheduling",
        "manage_overbooking_policy",
        "view_reports",
        "export_reports",
        "view_audit_log",
        "view_patient_phi",
        "manage_config",
    },
    "billing_staff": {"export_reports"},
}


@dataclass
class User:
    """A staff user or patient acting against the system (for RBAC checks)."""

    user_id: str
    role: str

    def has_permission(self, permission: str) -> bool:
        return permission in ROLE_PERMISSIONS.get(self.role, set())


# ---------------------------------------------------------------------------
# Domain entities
# ---------------------------------------------------------------------------

@dataclass
class Patient:
    patient_id: str
    email: Optional[str] = None
    phone: Optional[str] = None
    status: str = "PENDING_OTP_VERIFICATION"
    otp: Optional[str] = None
    otp_expires_at: Optional[datetime] = None
    failed_login_attempts: int = 0
    is_new_patient: bool = True
    referrals: Set[str] = field(default_factory=set)  # visit_type_ids with referral on file
    notification_preferences: Dict[str, bool] = field(default_factory=lambda: {"sms": True, "email": True})
    preferred_language: str = "en"
    emergency_contact: Optional[dict] = None


@dataclass
class VisitType:
    visit_type_id: str
    name: str
    duration_minutes: int = 30
    instant_booking: bool = True
    requires_referral: bool = False
    new_patients_allowed: bool = True
    overbooking_allowed: bool = False
    reschedule_cancel_window_hours: int = 24


@dataclass
class Slot:
    slot_id: str
    provider_id: str
    location_id: str
    start_time: datetime
    visit_type_id: str
    status: str = "AVAILABLE"  # AVAILABLE, BOOKED


APPOINTMENT_STATES = [
    "REQUESTED",
    "SCHEDULED",
    "CONFIRMED",
    "CHECKED_IN",
    "IN_ROOM",
    "COMPLETED",
    "CANCELLED",
    "NO_SHOW",
]

# Allowed forward transitions (FR-108)
_ALLOWED_TRANSITIONS = {
    "REQUESTED": {"SCHEDULED", "CANCELLED"},
    "SCHEDULED": {"CONFIRMED", "CANCELLED", "NO_SHOW", "CHECKED_IN"},
    "CONFIRMED": {"CHECKED_IN", "CANCELLED", "NO_SHOW"},
    "CHECKED_IN": {"IN_ROOM", "CANCELLED"},
    "IN_ROOM": {"COMPLETED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
    "NO_SHOW": set(),
}


@dataclass
class Appointment:
    appointment_id: str
    patient_id: str
    slot_id: str
    visit_type_id: str
    status: str = "SCHEDULED"
    overbooked: bool = False
    overbooking_justification: Optional[str] = None
    cancel_reason_code: Optional[str] = None
    cancel_reason_text: Optional[str] = None

    def transition_to(self, new_status: str) -> None:
        allowed = _ALLOWED_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise ValidationError(
                f"Invalid transition {self.status} -> {new_status}"
            )
        self.status = new_status


@dataclass
class WaitlistEntry:
    waitlist_entry_id: str
    patient_id: str
    visit_type_id: str
    acceptable_provider_ids: Optional[Set[str]] = None
    acceptable_location_ids: Optional[Set[str]] = None
    status: str = "ACTIVE"  # ACTIVE, FULFILLED


@dataclass
class WaitlistOffer:
    offer_id: str
    waitlist_entry_id: str
    slot_id: str
    status: str = "PENDING"  # PENDING, ACCEPTED, DECLINED, EXPIRED
    expires_at: Optional[datetime] = None


@dataclass
class Task:
    task_id: str
    care_plan_id: str
    description: str
    owner_type: str = "PATIENT"
    due_date: Optional[datetime] = None
    priority: str = "NORMAL"
    status: str = "OPEN"  # OPEN, COMPLETED, OVERDUE


@dataclass
class CarePlan:
    care_plan_id: str
    appointment_id: str
    goals: List[str] = field(default_factory=list)
    interventions: List[str] = field(default_factory=list)
    task_ids: List[str] = field(default_factory=list)


@dataclass
class Notification:
    notification_id: str
    patient_id: str
    template: str
    channel: str
    status: str = "PENDING"  # PENDING, SENT, SUPPRESSED_OPT_OUT, DELIVERED


@dataclass
class AuditEntry:
    actor: str
    entity_type: str
    entity_id: str
    action: str
    before: Optional[dict]
    after: Optional[dict]
    justification: Optional[str]
    timestamp: datetime


# ---------------------------------------------------------------------------
# The system facade
# ---------------------------------------------------------------------------

class OSCSSystem:
    """In-memory reference implementation of the OSCS API surface."""

    def __init__(self) -> None:
        self._ids = itertools.count(1)
        self.patients: Dict[str, Patient] = {}
        self.visit_types: Dict[str, VisitType] = {}
        self.slots: Dict[str, Slot] = {}
        self.appointments: Dict[str, Appointment] = {}
        self.waitlist_entries: Dict[str, WaitlistEntry] = {}
        self.waitlist_offers: Dict[str, WaitlistOffer] = {}
        self.care_plans: Dict[str, CarePlan] = {}
        self.tasks: Dict[str, Task] = {}
        self.notifications: Dict[str, Notification] = {}
        self.audit_log: List[AuditEntry] = []
        self._max_failed_logins = 3

    # -- id helper ----------------------------------------------------
    def _new_id(self, prefix: str) -> str:
        return f"{prefix}_{next(self._ids)}_{uuid.uuid4().hex[:6]}"

    def _audit(self, actor, entity_type, entity_id, action, before, after,
               justification=None, now: Optional[datetime] = None) -> None:
        self.audit_log.append(AuditEntry(
            actor=actor.user_id if isinstance(actor, User) else (actor or "system"),
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            before=before,
            after=after,
            justification=justification,
            timestamp=now or datetime.now(),
        ))

    def _require_permission(self, actor: Optional[User], permission: str) -> None:
        if actor is None:
            return  # unauthenticated/system calls used only in test setup
        if not actor.has_permission(permission):
            raise ForbiddenError(f"Role '{actor.role}' lacks permission '{permission}'")

    # -- FR-001: registration / identity -------------------------------
    def register_patient(self, email: Optional[str] = None, phone: Optional[str] = None,
                          otp: str = "000000", now: Optional[datetime] = None) -> Patient:
        if not email and not phone:
            raise ValidationError("email or phone is required")
        patient = Patient(
            patient_id=self._new_id("pat"),
            email=email,
            phone=phone,
            otp=otp,
            otp_expires_at=(now or datetime.now()) + timedelta(minutes=10),
        )
        self.patients[patient.patient_id] = patient
        self._audit("system", "PATIENT", patient.patient_id, "CREATE", None,
                     {"status": patient.status}, now=now)
        return patient

    def verify_otp(self, patient_id: str, otp: str, now: Optional[datetime] = None) -> Patient:
        patient = self._get_patient_or_404(patient_id)
        now = now or datetime.now()
        if patient.otp_expires_at and now > patient.otp_expires_at:
            raise ExpiredError("OTP expired")
        if otp != patient.otp:
            raise ValidationError("Invalid OTP")
        before = {"status": patient.status}
        patient.status = "ACTIVE"
        self._audit("system", "PATIENT", patient_id, "OTP_VERIFIED", before,
                     {"status": patient.status}, now=now)
        return patient

    def login(self, patient_id: str, password_correct: bool,
              now: Optional[datetime] = None) -> str:
        patient = self._get_patient_or_404(patient_id)
        if patient.failed_login_attempts >= self._max_failed_logins:
            raise RateLimitedError("Too many failed login attempts")
        if not password_correct:
            patient.failed_login_attempts += 1
            self._audit(patient_id, "AUTH", patient_id, "LOGIN_FAILED", None, None, now=now)
            raise ValidationError("Invalid credentials")
        patient.failed_login_attempts = 0
        self._audit(patient_id, "AUTH", patient_id, "LOGIN_SUCCESS", None, None, now=now)
        return f"token-for-{patient_id}"

    # -- FR-002: profile -------------------------------------------------
    def update_profile(self, patient_id: str, **fields) -> Patient:
        patient = self._get_patient_or_404(patient_id)
        before = dict(patient.__dict__)
        for key, value in fields.items():
            if hasattr(patient, key):
                setattr(patient, key, value)
        self._audit(patient_id, "PATIENT", patient_id, "UPDATE", before,
                     dict(patient.__dict__))
        return patient

    # -- setup helpers (admin-only in a real system; unguarded here) -----
    def add_visit_type(self, **kwargs) -> VisitType:
        vt = VisitType(visit_type_id=self._new_id("vt"), **kwargs)
        self.visit_types[vt.visit_type_id] = vt
        return vt

    def add_slot(self, provider_id: str, location_id: str, start_time: datetime,
                 visit_type_id: str) -> Slot:
        slot = Slot(
            slot_id=self._new_id("slot"),
            provider_id=provider_id,
            location_id=location_id,
            start_time=start_time,
            visit_type_id=visit_type_id,
        )
        self.slots[slot.slot_id] = slot
        return slot

    # -- FR-003 / FR-102 / FR-107: search & booking ----------------------
    def search_availability(self, visit_type_id: str, location_id: Optional[str] = None,
                             provider_id: Optional[str] = None) -> List[Slot]:
        results = []
        for slot in self.slots.values():
            if slot.visit_type_id != visit_type_id or slot.status != "AVAILABLE":
                continue
            if location_id and slot.location_id != location_id:
                continue
            if provider_id and slot.provider_id != provider_id:
                continue
            results.append(slot)
        return results

    def book_appointment(self, patient_id: str, slot_id: str, visit_type_id: str,
                          now: Optional[datetime] = None) -> Appointment:
        patient = self._get_patient_or_404(patient_id)
        visit_type = self._get_visit_type_or_404(visit_type_id)
        slot = self._get_slot_or_404(slot_id)

        if slot.status != "AVAILABLE":
            raise ConflictError("Slot is already booked")

        if visit_type.requires_referral and visit_type_id not in patient.referrals:
            raise UnprocessableError("Referral required for this visit type")
        if not visit_type.new_patients_allowed and patient.is_new_patient:
            raise UnprocessableError("Visit type restricted to established patients")

        slot.status = "BOOKED"
        status = "SCHEDULED" if visit_type.instant_booking else "REQUESTED"
        appt = Appointment(
            appointment_id=self._new_id("appt"),
            patient_id=patient_id,
            slot_id=slot_id,
            visit_type_id=visit_type_id,
            status=status,
        )
        self.appointments[appt.appointment_id] = appt
        self._audit(patient_id, "APPOINTMENT", appt.appointment_id, "CREATE", None,
                     {"status": appt.status}, now=now)
        return appt

    # -- FR-004: reschedule / cancel -------------------------------------
    def _within_policy_window(self, appt: Appointment, now: datetime) -> bool:
        slot = self.slots[appt.slot_id]
        visit_type = self.visit_types[appt.visit_type_id]
        cutoff = slot.start_time - timedelta(hours=visit_type.reschedule_cancel_window_hours)
        return now <= cutoff

    def reschedule_appointment(self, appointment_id: str, new_slot_id: str,
                                now: Optional[datetime] = None) -> Appointment:
        now = now or datetime.now()
        appt = self._get_appointment_or_404(appointment_id)
        if not self._within_policy_window(appt, now):
            raise ForbiddenError("Outside reschedule policy window")
        new_slot = self._get_slot_or_404(new_slot_id)
        if new_slot.status != "AVAILABLE":
            raise ConflictError("Requested new slot is not available")

        old_slot = self.slots[appt.slot_id]
        old_slot.status = "AVAILABLE"
        new_slot.status = "BOOKED"
        before = {"slot_id": appt.slot_id}
        appt.slot_id = new_slot_id
        self._audit(appt.patient_id, "APPOINTMENT", appointment_id, "RESCHEDULE",
                     before, {"slot_id": appt.slot_id}, now=now)
        return appt

    def cancel_appointment(self, appointment_id: str, reason_code: str,
                            reason_text: Optional[str] = None,
                            now: Optional[datetime] = None,
                            enforce_policy_window: bool = True) -> Appointment:
        now = now or datetime.now()
        appt = self._get_appointment_or_404(appointment_id)
        if enforce_policy_window and not self._within_policy_window(appt, now):
            raise ForbiddenError("Outside cancellation policy window")

        before = {"status": appt.status}
        appt.transition_to("CANCELLED")
        appt.cancel_reason_code = reason_code
        appt.cancel_reason_text = reason_text
        self.slots[appt.slot_id].status = "AVAILABLE"
        self._audit(appt.patient_id, "APPOINTMENT", appointment_id, "CANCEL", before,
                     {"status": appt.status, "reason": reason_code}, now=now)

        offer = self._trigger_waitlist_offer(appt.visit_type_id, appt.slot_id, now=now)
        return appt, offer  # type: ignore[return-value]

    # -- FR-105: waitlist --------------------------------------------------
    def join_waitlist(self, patient_id: str, visit_type_id: str,
                       acceptable_provider_ids: Optional[Set[str]] = None,
                       acceptable_location_ids: Optional[Set[str]] = None) -> WaitlistEntry:
        self._get_patient_or_404(patient_id)
        entry = WaitlistEntry(
            waitlist_entry_id=self._new_id("wl"),
            patient_id=patient_id,
            visit_type_id=visit_type_id,
            acceptable_provider_ids=acceptable_provider_ids,
            acceptable_location_ids=acceptable_location_ids,
        )
        self.waitlist_entries[entry.waitlist_entry_id] = entry
        return entry

    def _trigger_waitlist_offer(self, visit_type_id: str, freed_slot_id: str,
                                 now: Optional[datetime] = None,
                                 expiry_minutes: int = 30) -> Optional[WaitlistOffer]:
        now = now or datetime.now()
        slot = self.slots[freed_slot_id]
        for entry in self.waitlist_entries.values():
            if entry.status != "ACTIVE" or entry.visit_type_id != visit_type_id:
                continue
            if entry.acceptable_provider_ids and slot.provider_id not in entry.acceptable_provider_ids:
                continue
            if entry.acceptable_location_ids and slot.location_id not in entry.acceptable_location_ids:
                continue
            offer = WaitlistOffer(
                offer_id=self._new_id("off"),
                waitlist_entry_id=entry.waitlist_entry_id,
                slot_id=freed_slot_id,
                expires_at=now + timedelta(minutes=expiry_minutes),
            )
            self.waitlist_offers[offer.offer_id] = offer
            return offer  # priority order: first matching active entry
        return None

    def respond_to_waitlist_offer(self, offer_id: str, accept: bool,
                                   now: Optional[datetime] = None) -> WaitlistOffer:
        now = now or datetime.now()
        offer = self.waitlist_offers.get(offer_id)
        if offer is None:
            raise NotFoundError("Offer not found")
        if offer.status != "PENDING":
            raise ConflictError("Offer already resolved")
        if now > offer.expires_at:
            offer.status = "EXPIRED"
            self.slots[offer.slot_id].status = "AVAILABLE"
            raise ExpiredError("Waitlist offer expired")

        if accept:
            slot = self.slots[offer.slot_id]
            if slot.status != "AVAILABLE":
                raise ConflictError("Slot no longer available")
            slot.status = "BOOKED"
            offer.status = "ACCEPTED"
            entry = self.waitlist_entries[offer.waitlist_entry_id]
            entry.status = "FULFILLED"
        else:
            offer.status = "DECLINED"
            self.slots[offer.slot_id].status = "AVAILABLE"
        return offer

    def expire_stale_offers(self, now: Optional[datetime] = None) -> List[WaitlistOffer]:
        """Sweep pending offers past expiry and release their slots (FR-105)."""
        now = now or datetime.now()
        expired = []
        for offer in self.waitlist_offers.values():
            if offer.status == "PENDING" and now > offer.expires_at:
                offer.status = "EXPIRED"
                self.slots[offer.slot_id].status = "AVAILABLE"
                expired.append(offer)
        return expired

    # -- FR-106: overbooking ------------------------------------------------
    def book_overbooked(self, patient_id: str, slot_id: str, visit_type_id: str,
                         justification: Optional[str], actor: Optional[User] = None,
                         now: Optional[datetime] = None) -> Appointment:
        self._require_permission(actor, "manage_scheduling")
        visit_type = self._get_visit_type_or_404(visit_type_id)
        if not visit_type.overbooking_allowed:
            raise ForbiddenError("Overbooking not permitted for this visit type")
        if not justification:
            raise ValidationError("Justification is required for overbooking")

        patient = self._get_patient_or_404(patient_id)
        slot = self._get_slot_or_404(slot_id)
        appt = Appointment(
            appointment_id=self._new_id("appt"),
            patient_id=patient_id,
            slot_id=slot_id,
            visit_type_id=visit_type_id,
            status="SCHEDULED",
            overbooked=True,
            overbooking_justification=justification,
        )
        self.appointments[appt.appointment_id] = appt
        self._audit(actor, "APPOINTMENT", appt.appointment_id, "OVERBOOK", None,
                     {"overbooked": True}, justification=justification, now=now)
        return appt

    # -- FR-202 / FR-203 / FR-108: check-in ----------------------------------
    def check_in(self, appointment_id: str, mode: str,
                 now: Optional[datetime] = None,
                 within_geofence: bool = True,
                 checkin_window_minutes: int = 30) -> Appointment:
        now = now or datetime.now()
        appt = self._get_appointment_or_404(appointment_id)
        slot = self.slots[appt.slot_id]

        if mode == "MOBILE_SELF":
            earliest = slot.start_time - timedelta(minutes=checkin_window_minutes)
            if now < earliest or now > slot.start_time:
                raise ForbiddenError("Outside mobile self check-in time window")
            if not within_geofence:
                raise ForbiddenError("Outside geo-fence for mobile self check-in")

        before = {"status": appt.status}
        appt.transition_to("CHECKED_IN")
        self._audit(appt.patient_id, "APPOINTMENT", appointment_id, "CHECK_IN", before,
                     {"status": appt.status}, now=now)
        return appt

    # -- FR-301 / FR-302 / FR-303: care plans & tasks ------------------------
    def create_care_plan(self, appointment_id: str, goals: List[str],
                          interventions: List[str], task_specs: List[dict],
                          actor: Optional[User] = None) -> CarePlan:
        self._require_permission(actor, "manage_care_plan")
        self._get_appointment_or_404(appointment_id)
        plan = CarePlan(care_plan_id=self._new_id("cp"), appointment_id=appointment_id,
                         goals=goals, interventions=interventions)
        for spec in task_specs:
            task = Task(task_id=self._new_id("task"), care_plan_id=plan.care_plan_id, **spec)
            self.tasks[task.task_id] = task
            plan.task_ids.append(task.task_id)
        self.care_plans[plan.care_plan_id] = plan
        return plan

    def update_task_status(self, task_id: str, status: str,
                            actor: Optional[User] = None) -> Task:
        self._require_permission(actor, "manage_tasks")
        task = self.tasks.get(task_id)
        if task is None:
            raise NotFoundError("Task not found")
        task.status = status
        return task

    def mark_overdue_tasks(self, now: Optional[datetime] = None) -> List[Task]:
        now = now or datetime.now()
        overdue = []
        for task in self.tasks.values():
            if task.status == "OPEN" and task.due_date and now > task.due_date:
                task.status = "OVERDUE"
                overdue.append(task)
        return overdue

    def schedule_next(self, care_plan_id: str, visit_type_id: str,
                       location_id: Optional[str] = None) -> List[Slot]:
        plan = self.care_plans.get(care_plan_id)
        if plan is None:
            raise NotFoundError("Care plan not found")
        return self.search_availability(visit_type_id, location_id=location_id)

    # -- FR-401 / FR-402: notifications ---------------------------------------
    def set_notification_preference(self, patient_id: str, channel: str, opted_in: bool) -> Patient:
        patient = self._get_patient_or_404(patient_id)
        patient.notification_preferences[channel] = opted_in
        return patient

    def send_notification(self, patient_id: str, template: str, channel: str) -> Notification:
        patient = self._get_patient_or_404(patient_id)
        notif = Notification(
            notification_id=self._new_id("notif"),
            patient_id=patient_id,
            template=template,
            channel=channel,
        )
        if not patient.notification_preferences.get(channel, False):
            notif.status = "SUPPRESSED_OPT_OUT"
        else:
            notif.status = "DELIVERED"
        self.notifications[notif.notification_id] = notif
        return notif

    def route_inbound_message(self, appointment_id: str, body: str) -> dict:
        body_normalized = body.strip().upper()
        if body_normalized == "CANCEL":
            self.cancel_appointment(appointment_id, reason_code="PATIENT_SMS_CANCEL",
                                     enforce_policy_window=False)
            return {"routed": "AUTOMATED_ACTION", "action": "CANCEL_APPOINTMENT"}
        return {"routed": "STAFF_INBOX", "action": None}

    # -- FR-503 / FR-603: reporting & audit -----------------------------------
    def export_report(self, actor: Optional[User]) -> str:
        self._require_permission(actor, "export_reports")
        self._audit(actor, "REPORT", "operational_report", "EXPORT", None, None)
        return "metric,value\nno_show_rate,0.08\n"

    def get_audit_log(self, actor: Optional[User] = None) -> List[AuditEntry]:
        self._require_permission(actor, "view_audit_log")
        return list(self.audit_log)

    def get_patient_phi(self, patient_id: str, actor: Optional[User]) -> Patient:
        self._require_permission(actor, "view_patient_phi")
        return self._get_patient_or_404(patient_id)

    # -- lookups -------------------------------------------------------------
    def _get_patient_or_404(self, patient_id: str) -> Patient:
        patient = self.patients.get(patient_id)
        if patient is None:
            raise NotFoundError(f"Patient {patient_id} not found")
        return patient

    def _get_visit_type_or_404(self, visit_type_id: str) -> VisitType:
        vt = self.visit_types.get(visit_type_id)
        if vt is None:
            raise NotFoundError(f"Visit type {visit_type_id} not found")
        return vt

    def _get_slot_or_404(self, slot_id: str) -> Slot:
        slot = self.slots.get(slot_id)
        if slot is None:
            raise NotFoundError(f"Slot {slot_id} not found")
        return slot

    def _get_appointment_or_404(self, appointment_id: str) -> Appointment:
        appt = self.appointments.get(appointment_id)
        if appt is None:
            raise NotFoundError(f"Appointment {appointment_id} not found")
        return appt
