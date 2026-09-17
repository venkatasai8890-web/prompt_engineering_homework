"""
Automated pytest tests for the OSCS mock reference implementation.

Each test's docstring references the corresponding Test Case ID from
homework2/01_test_cases.md and the Functional Requirement (FR-###) from
the PRD that it exercises. All data used is synthetic (see conftest.py) --
no real patient information / PHI is used anywhere in this suite.
"""

from datetime import timedelta

import pytest

from mock_oscs_api import (
    ConflictError,
    ExpiredError,
    ForbiddenError,
    NotFoundError,
    RateLimitedError,
    UnprocessableError,
    ValidationError,
)


# ===========================================================================
# A. Patient registration & identity -- FR-001
# ===========================================================================

class TestRegistrationAndAuth:

    def test_register_patient_creates_pending_account(self, system, now):
        """TC-A-001: registering creates an account pending OTP verification."""
        patient = system.register_patient(
            email="synthetic.reg001@example-test.invalid",
            phone="+15550000099",
            otp="654321",
            now=now,
        )
        assert patient.status == "PENDING_OTP_VERIFICATION"
        assert patient.patient_id in system.patients

    def test_verify_otp_success_activates_account(self, system, now):
        """TC-A-001: correct OTP activates the account and is audited."""
        patient = system.register_patient(email="synthetic.reg002@example-test.invalid",
                                            otp="123123", now=now)
        activated = system.verify_otp(patient.patient_id, "123123", now=now)
        assert activated.status == "ACTIVE"
        audited_actions = [e.action for e in system.audit_log if e.entity_id == patient.patient_id]
        assert "OTP_VERIFIED" in audited_actions

    def test_verify_otp_failure_invalid_otp_rejected(self, system, now):
        """TC-A-002: registration/activation fails with an incorrect OTP."""
        patient = system.register_patient(email="synthetic.reg003@example-test.invalid",
                                            otp="999999", now=now)
        with pytest.raises(ValidationError):
            system.verify_otp(patient.patient_id, "000000", now=now)
        assert patient.status == "PENDING_OTP_VERIFICATION"

    def test_verify_otp_expired_is_rejected(self, system, now):
        """Validation: an OTP submitted after its expiry window is rejected."""
        patient = system.register_patient(email="synthetic.reg004@example-test.invalid",
                                            otp="777777", now=now)
        too_late = now + timedelta(minutes=15)
        with pytest.raises(ExpiredError):
            system.verify_otp(patient.patient_id, "777777", now=too_late)

    def test_login_rate_limited_after_repeated_failures(self, system, now, synthetic_patient):
        """TC-A-003: repeated failed logins are rate-limited."""
        for _ in range(3):
            with pytest.raises(ValidationError):
                system.login(synthetic_patient.patient_id, password_correct=False, now=now)
        with pytest.raises(RateLimitedError):
            system.login(synthetic_patient.patient_id, password_correct=False, now=now)

    def test_login_success_resets_failed_attempts(self, system, now, synthetic_patient):
        """Positive login clears the failed-attempt counter."""
        with pytest.raises(ValidationError):
            system.login(synthetic_patient.patient_id, password_correct=False, now=now)
        token = system.login(synthetic_patient.patient_id, password_correct=True, now=now)
        assert token.startswith("token-for-")
        assert synthetic_patient.failed_login_attempts == 0


# ===========================================================================
# B. Profile management -- FR-002
# ===========================================================================

class TestProfile:

    def test_update_profile_persists_changes(self, system, synthetic_patient):
        """TC-A-004/A-005: profile updates (language, emergency contact) persist."""
        updated = system.update_profile(
            synthetic_patient.patient_id,
            preferred_language="es",
            emergency_contact={"name": "Synthetic Contact", "phone": "+15550000098"},
        )
        assert updated.preferred_language == "es"
        assert updated.emergency_contact["name"] == "Synthetic Contact"


# ===========================================================================
# C. Appointment search & self-scheduling -- FR-003, FR-102, FR-107
# ===========================================================================

class TestBooking:

    def test_book_instant_visit_type_succeeds(self, system, synthetic_patient,
                                               standard_visit_type, make_slot, now):
        """TC-B-001: instant-booking-eligible visit type books immediately."""
        slot = make_slot(standard_visit_type)
        appt = system.book_appointment(synthetic_patient.patient_id, slot.slot_id,
                                        standard_visit_type.visit_type_id, now=now)
        assert appt.status == "SCHEDULED"
        assert system.slots[slot.slot_id].status == "BOOKED"

    def test_book_request_and_approve_visit_type_creates_requested_state(
            self, system, synthetic_patient, request_and_approve_visit_type, make_slot, now):
        """TC-B-002: non-instant visit types land in REQUESTED, not SCHEDULED."""
        slot = make_slot(request_and_approve_visit_type)
        appt = system.book_appointment(synthetic_patient.patient_id, slot.slot_id,
                                        request_and_approve_visit_type.visit_type_id, now=now)
        assert appt.status == "REQUESTED"

    def test_double_booking_same_slot_raises_conflict(self, system, synthetic_patient,
                                                        synthetic_new_patient,
                                                        standard_visit_type, make_slot, now):
        """TC-B-003: a second booking attempt on an already-booked slot conflicts."""
        slot = make_slot(standard_visit_type)
        system.book_appointment(synthetic_patient.patient_id, slot.slot_id,
                                 standard_visit_type.visit_type_id, now=now)
        with pytest.raises(ConflictError):
            system.book_appointment(synthetic_new_patient.patient_id, slot.slot_id,
                                     standard_visit_type.visit_type_id, now=now)

    def test_booking_blocked_without_required_referral(self, system, synthetic_new_patient,
                                                         referral_visit_type, make_slot, now):
        """TC-B-004: booking is blocked when a referral is required but absent."""
        slot = make_slot(referral_visit_type)
        with pytest.raises(UnprocessableError):
            system.book_appointment(synthetic_new_patient.patient_id, slot.slot_id,
                                     referral_visit_type.visit_type_id, now=now)

    def test_booking_succeeds_with_referral_on_file(
            self, system, synthetic_established_patient_with_referral,
            referral_visit_type, make_slot, now):
        """Positive counterpart to TC-B-004: referral present -> booking succeeds."""
        slot = make_slot(referral_visit_type)
        appt = system.book_appointment(
            synthetic_established_patient_with_referral.patient_id, slot.slot_id,
            referral_visit_type.visit_type_id, now=now)
        assert appt.status == "SCHEDULED"

    def test_booking_blocked_for_new_patient_restricted_visit_type(
            self, system, synthetic_new_patient, established_patients_only_visit_type,
            make_slot, now):
        """TC-B-005: new-patient vs established-patient rule is enforced."""
        slot = make_slot(established_patients_only_visit_type)
        with pytest.raises(UnprocessableError):
            system.book_appointment(synthetic_new_patient.patient_id, slot.slot_id,
                                     established_patients_only_visit_type.visit_type_id, now=now)


# ===========================================================================
# D. Provider availability / resource conflicts -- FR-101, FR-102, FR-104
# ===========================================================================

class TestAvailabilitySearch:

    def test_search_availability_filters_by_provider_and_location(
            self, system, standard_visit_type, make_slot,
            synthetic_provider_id, synthetic_second_provider_id, synthetic_location_id):
        """FR-101/102: availability search returns only matching provider/location slots."""
        make_slot(standard_visit_type, provider_id=synthetic_provider_id)
        make_slot(standard_visit_type, provider_id=synthetic_second_provider_id)

        results = system.search_availability(
            standard_visit_type.visit_type_id, provider_id=synthetic_provider_id)

        assert len(results) == 1
        assert results[0].provider_id == synthetic_provider_id

    def test_booked_slot_no_longer_appears_in_availability_search(
            self, system, synthetic_patient, standard_visit_type, make_slot, now):
        """FR-104: once booked, a slot is removed from available search results."""
        slot = make_slot(standard_visit_type)
        system.book_appointment(synthetic_patient.patient_id, slot.slot_id,
                                 standard_visit_type.visit_type_id, now=now)
        results = system.search_availability(standard_visit_type.visit_type_id)
        assert slot.slot_id not in [s.slot_id for s in results]


# ===========================================================================
# E. Reschedule & cancellation -- FR-004
# ===========================================================================

class TestRescheduleAndCancel:

    def test_reschedule_within_policy_window_succeeds(self, system, synthetic_patient,
                                                        standard_visit_type, make_slot, now):
        """TC-C-001: reschedule succeeds when within the configured policy window."""
        original = make_slot(standard_visit_type, hours_from_now=72)
        new_slot = make_slot(standard_visit_type, hours_from_now=96)
        appt = system.book_appointment(synthetic_patient.patient_id, original.slot_id,
                                        standard_visit_type.visit_type_id, now=now)

        updated = system.reschedule_appointment(appt.appointment_id, new_slot.slot_id, now=now)

        assert updated.slot_id == new_slot.slot_id
        assert system.slots[original.slot_id].status == "AVAILABLE"
        assert system.slots[new_slot.slot_id].status == "BOOKED"

    def test_reschedule_outside_policy_window_blocked(self, system, synthetic_patient,
                                                        standard_visit_type, make_slot, now):
        """TC-C-002: reschedule is blocked once inside the policy cutoff window."""
        original = make_slot(standard_visit_type, hours_from_now=2)  # inside 24h window
        new_slot = make_slot(standard_visit_type, hours_from_now=48)
        appt = system.book_appointment(synthetic_patient.patient_id, original.slot_id,
                                        standard_visit_type.visit_type_id, now=now)

        with pytest.raises(ForbiddenError):
            system.reschedule_appointment(appt.appointment_id, new_slot.slot_id, now=now)

    def test_cancel_appointment_captures_reason(self, system, synthetic_patient,
                                                 standard_visit_type, make_slot, now):
        """TC-C-003: cancellation stores the structured reason and audits the transition."""
        slot = make_slot(standard_visit_type, hours_from_now=72)
        appt = system.book_appointment(synthetic_patient.patient_id, slot.slot_id,
                                        standard_visit_type.visit_type_id, now=now)

        cancelled, _offer = system.cancel_appointment(
            appt.appointment_id, reason_code="SCHEDULE_CONFLICT",
            reason_text="Synthetic test conflict", now=now)

        assert cancelled.status == "CANCELLED"
        assert cancelled.cancel_reason_code == "SCHEDULE_CONFLICT"
        assert any(e.action == "CANCEL" for e in system.audit_log)


# ===========================================================================
# F. Waitlist -- FR-105
# ===========================================================================

class TestWaitlist:

    def test_cancellation_triggers_matching_waitlist_offer(
            self, system, synthetic_patient, synthetic_new_patient,
            standard_visit_type, make_slot, synthetic_provider_id, now):
        """TC-C-004: a cancellation triggers an offer to a matching waitlisted patient."""
        slot = make_slot(standard_visit_type, hours_from_now=72)
        appt = system.book_appointment(synthetic_patient.patient_id, slot.slot_id,
                                        standard_visit_type.visit_type_id, now=now)
        system.join_waitlist(synthetic_new_patient.patient_id,
                              standard_visit_type.visit_type_id,
                              acceptable_provider_ids={synthetic_provider_id})

        _cancelled, offer = system.cancel_appointment(
            appt.appointment_id, reason_code="PATIENT_REQUEST", now=now)

        assert offer is not None
        assert offer.status == "PENDING"
        assert offer.slot_id == slot.slot_id

    def test_waitlist_offer_expires_and_releases_slot(
            self, system, synthetic_patient, synthetic_new_patient,
            standard_visit_type, make_slot, synthetic_provider_id, now):
        """TC-C-005: an unanswered waitlist offer expires and the slot is released."""
        slot = make_slot(standard_visit_type, hours_from_now=72)
        appt = system.book_appointment(synthetic_patient.patient_id, slot.slot_id,
                                        standard_visit_type.visit_type_id, now=now)
        system.join_waitlist(synthetic_new_patient.patient_id,
                              standard_visit_type.visit_type_id,
                              acceptable_provider_ids={synthetic_provider_id})
        _cancelled, offer = system.cancel_appointment(
            appt.appointment_id, reason_code="PATIENT_REQUEST", now=now)

        after_expiry = now + timedelta(minutes=45)
        with pytest.raises(ExpiredError):
            system.respond_to_waitlist_offer(offer.offer_id, accept=True, now=after_expiry)
        assert system.slots[slot.slot_id].status == "AVAILABLE"

    def test_waitlist_offer_accepted_before_expiry_books_patient(
            self, system, synthetic_patient, synthetic_new_patient,
            standard_visit_type, make_slot, synthetic_provider_id, now):
        """TC-C-006: accepting the offer before expiry books the waitlisted patient."""
        slot = make_slot(standard_visit_type, hours_from_now=72)
        appt = system.book_appointment(synthetic_patient.patient_id, slot.slot_id,
                                        standard_visit_type.visit_type_id, now=now)
        system.join_waitlist(synthetic_new_patient.patient_id,
                              standard_visit_type.visit_type_id,
                              acceptable_provider_ids={synthetic_provider_id})
        _cancelled, offer = system.cancel_appointment(
            appt.appointment_id, reason_code="PATIENT_REQUEST", now=now)

        soon = now + timedelta(minutes=5)
        accepted = system.respond_to_waitlist_offer(offer.offer_id, accept=True, now=soon)

        assert accepted.status == "ACCEPTED"
        assert system.slots[slot.slot_id].status == "BOOKED"


# ===========================================================================
# G. Overbooking -- FR-106
# ===========================================================================

class TestOverbooking:

    def test_overbooking_with_justification_succeeds_and_is_flagged(
            self, system, synthetic_patient, overbookable_visit_type, make_slot,
            front_desk_user, now):
        """TC-D-003: overbooking with a justification succeeds and is flagged + audited."""
        slot = make_slot(overbookable_visit_type)
        appt = system.book_overbooked(
            synthetic_patient.patient_id, slot.slot_id, overbookable_visit_type.visit_type_id,
            justification="Synthetic urgent same-day escalation", actor=front_desk_user, now=now)

        assert appt.overbooked is True
        assert any(e.action == "OVERBOOK" and e.justification for e in system.audit_log)

    def test_overbooking_without_justification_rejected(
            self, system, synthetic_patient, overbookable_visit_type, make_slot,
            front_desk_user, now):
        """TC-D-004: overbooking without a justification is rejected."""
        slot = make_slot(overbookable_visit_type)
        with pytest.raises(ValidationError):
            system.book_overbooked(
                synthetic_patient.patient_id, slot.slot_id,
                overbookable_visit_type.visit_type_id, justification=None,
                actor=front_desk_user, now=now)

    def test_overbooking_rejected_when_policy_disallows(
            self, system, synthetic_patient, standard_visit_type, make_slot,
            front_desk_user, now):
        """TC-D-005: overbooking is rejected entirely when policy disallows it."""
        slot = make_slot(standard_visit_type)  # overbooking_allowed=False
        with pytest.raises(ForbiddenError):
            system.book_overbooked(
                synthetic_patient.patient_id, slot.slot_id, standard_visit_type.visit_type_id,
                justification="Synthetic reason", actor=front_desk_user, now=now)

    def test_overbooking_requires_manage_scheduling_permission(
            self, system, synthetic_patient, overbookable_visit_type, make_slot,
            patient_role_user, now):
        """RBAC: a caller without 'manage_scheduling' cannot perform an overbooking."""
        slot = make_slot(overbookable_visit_type)
        with pytest.raises(ForbiddenError):
            system.book_overbooked(
                synthetic_patient.patient_id, slot.slot_id,
                overbookable_visit_type.visit_type_id, justification="Synthetic reason",
                actor=patient_role_user, now=now)


# ===========================================================================
# H. Appointment lifecycle states -- FR-108
# ===========================================================================

class TestLifecycleStates:

    def test_valid_lifecycle_transition_sequence(self, system, synthetic_patient,
                                                  standard_visit_type, make_slot, now):
        """TC-E-001: a valid forward sequence of state transitions succeeds."""
        slot = make_slot(standard_visit_type)
        appt = system.book_appointment(synthetic_patient.patient_id, slot.slot_id,
                                        standard_visit_type.visit_type_id, now=now)
        appt.transition_to("CONFIRMED")
        appt.transition_to("CHECKED_IN")
        appt.transition_to("IN_ROOM")
        appt.transition_to("COMPLETED")
        assert appt.status == "COMPLETED"

    def test_invalid_lifecycle_transition_rejected(self, system, synthetic_patient,
                                                     standard_visit_type, make_slot, now):
        """TC-E-002: an invalid transition (skipping required states) is rejected."""
        slot = make_slot(standard_visit_type)
        appt = system.book_appointment(synthetic_patient.patient_id, slot.slot_id,
                                        standard_visit_type.visit_type_id, now=now)
        with pytest.raises(ValidationError):
            appt.transition_to("COMPLETED")  # cannot skip CONFIRMED/CHECKED_IN/IN_ROOM

    def test_no_show_transition(self, system, synthetic_patient, standard_visit_type,
                                 make_slot, now):
        """TC-E-003: an appointment can be marked No-show from Scheduled."""
        slot = make_slot(standard_visit_type)
        appt = system.book_appointment(synthetic_patient.patient_id, slot.slot_id,
                                        standard_visit_type.visit_type_id, now=now)
        appt.transition_to("NO_SHOW")
        assert appt.status == "NO_SHOW"


# ===========================================================================
# I. Intake / check-in -- FR-202, FR-203
# ===========================================================================

class TestCheckIn:

    def test_front_desk_check_in_success(self, system, synthetic_patient,
                                          standard_visit_type, make_slot, now):
        """TC-F-005: front-desk check-in updates state to CHECKED_IN."""
        slot = make_slot(standard_visit_type)
        appt = system.book_appointment(synthetic_patient.patient_id, slot.slot_id,
                                        standard_visit_type.visit_type_id, now=now)
        checked_in = system.check_in(appt.appointment_id, mode="FRONT_DESK", now=now)
        assert checked_in.status == "CHECKED_IN"

    def test_mobile_self_check_in_within_window_succeeds(
            self, system, synthetic_patient, standard_visit_type, make_slot, now):
        """TC-F-006: mobile self check-in succeeds within the allowed time window."""
        slot = make_slot(standard_visit_type, hours_from_now=1)  # start_time = now + 1h
        appt = system.book_appointment(synthetic_patient.patient_id, slot.slot_id,
                                        standard_visit_type.visit_type_id, now=now)
        just_before_start = slot.start_time - timedelta(minutes=10)
        checked_in = system.check_in(appt.appointment_id, mode="MOBILE_SELF",
                                      now=just_before_start, within_geofence=True)
        assert checked_in.status == "CHECKED_IN"

    def test_mobile_self_check_in_outside_time_window_blocked(
            self, system, synthetic_patient, standard_visit_type, make_slot, now):
        """TC-F-007: mobile self check-in is blocked outside the allowed time window."""
        slot = make_slot(standard_visit_type, hours_from_now=5)
        appt = system.book_appointment(synthetic_patient.patient_id, slot.slot_id,
                                        standard_visit_type.visit_type_id, now=now)
        too_early = slot.start_time - timedelta(hours=2)
        with pytest.raises(ForbiddenError):
            system.check_in(appt.appointment_id, mode="MOBILE_SELF", now=too_early)

    def test_mobile_self_check_in_outside_geofence_blocked(
            self, system, synthetic_patient, standard_visit_type, make_slot, now):
        """TC-F-007 (variant): mobile self check-in is blocked outside the geo-fence."""
        slot = make_slot(standard_visit_type, hours_from_now=1)
        appt = system.book_appointment(synthetic_patient.patient_id, slot.slot_id,
                                        standard_visit_type.visit_type_id, now=now)
        just_before_start = slot.start_time - timedelta(minutes=10)
        with pytest.raises(ForbiddenError):
            system.check_in(appt.appointment_id, mode="MOBILE_SELF",
                             now=just_before_start, within_geofence=False)


# ===========================================================================
# J. Care plans & tasks -- FR-301, FR-302, FR-303
# ===========================================================================

class TestCareManagement:

    def test_create_care_plan_with_tasks(self, system, synthetic_patient, standard_visit_type,
                                          make_slot, clinician_user, now):
        """TC-G-001/G-002: a care plan with tasks can be created and linked to an encounter."""
        slot = make_slot(standard_visit_type)
        appt = system.book_appointment(synthetic_patient.patient_id, slot.slot_id,
                                        standard_visit_type.visit_type_id, now=now)
        plan = system.create_care_plan(
            appt.appointment_id,
            goals=["Synthetic goal: improve mobility"],
            interventions=["Synthetic intervention: PT referral"],
            task_specs=[{
                "description": "Synthetic follow-up lab draw",
                "owner_type": "PATIENT",
                "due_date": now + timedelta(days=14),
                "priority": "HIGH",
            }],
            actor=clinician_user,
        )
        assert plan.appointment_id == appt.appointment_id
        assert len(plan.task_ids) == 1

    def test_update_task_status_completed(self, system, synthetic_patient, standard_visit_type,
                                           make_slot, clinician_user, nurse_user, now):
        """TC-G-002: a task's status can be updated by an authorized care team member."""
        slot = make_slot(standard_visit_type)
        appt = system.book_appointment(synthetic_patient.patient_id, slot.slot_id,
                                        standard_visit_type.visit_type_id, now=now)
        plan = system.create_care_plan(
            appt.appointment_id, goals=[], interventions=[],
            task_specs=[{"description": "Synthetic task", "due_date": now + timedelta(days=7)}],
            actor=clinician_user)
        task_id = plan.task_ids[0]

        updated = system.update_task_status(task_id, "COMPLETED", actor=nurse_user)
        assert updated.status == "COMPLETED"

    def test_overdue_task_is_escalated(self, system, synthetic_patient, standard_visit_type,
                                        make_slot, clinician_user, now):
        """TC-G-003: a task past its due date is escalated to OVERDUE."""
        slot = make_slot(standard_visit_type)
        appt = system.book_appointment(synthetic_patient.patient_id, slot.slot_id,
                                        standard_visit_type.visit_type_id, now=now)
        plan = system.create_care_plan(
            appt.appointment_id, goals=[], interventions=[],
            task_specs=[{"description": "Synthetic overdue task",
                         "due_date": now + timedelta(days=1)}],
            actor=clinician_user)

        overdue = system.mark_overdue_tasks(now=now + timedelta(days=3))
        assert plan.task_ids[0] in [t.task_id for t in overdue]
        assert system.tasks[plan.task_ids[0]].status == "OVERDUE"

    def test_schedule_next_returns_available_follow_up_slots(
            self, system, synthetic_patient, standard_visit_type, make_slot,
            clinician_user, now):
        """TC-G-004: 'schedule next' surfaces available follow-up slots from a care plan."""
        slot = make_slot(standard_visit_type)
        appt = system.book_appointment(synthetic_patient.patient_id, slot.slot_id,
                                        standard_visit_type.visit_type_id, now=now)
        plan = system.create_care_plan(appt.appointment_id, goals=[], interventions=[],
                                        task_specs=[], actor=clinician_user)
        follow_up_slot = make_slot(standard_visit_type, hours_from_now=200)

        suggestions = system.schedule_next(plan.care_plan_id, standard_visit_type.visit_type_id)
        assert follow_up_slot.slot_id in [s.slot_id for s in suggestions]


# ===========================================================================
# K. Notifications & messaging -- FR-401, FR-402
# ===========================================================================

class TestNotifications:

    def test_notification_delivered_when_opted_in(self, system, synthetic_patient):
        """TC-H-001: a notification is delivered when the patient has opted in."""
        notif = system.send_notification(synthetic_patient.patient_id, "CONFIRMATION", "sms")
        assert notif.status == "DELIVERED"

    def test_notification_suppressed_when_opted_out(self, system, synthetic_patient):
        """TC-H-003: a notification is suppressed on a channel the patient opted out of."""
        system.set_notification_preference(synthetic_patient.patient_id, "sms", False)
        notif = system.send_notification(synthetic_patient.patient_id, "REMINDER", "sms")
        assert notif.status == "SUPPRESSED_OPT_OUT"

    def test_inbound_cancel_keyword_triggers_automated_cancellation(
            self, system, synthetic_patient, standard_visit_type, make_slot, now):
        """TC-H-004: replying CANCEL via SMS triggers automated appointment cancellation."""
        slot = make_slot(standard_visit_type, hours_from_now=72)
        appt = system.book_appointment(synthetic_patient.patient_id, slot.slot_id,
                                        standard_visit_type.visit_type_id, now=now)

        result = system.route_inbound_message(appt.appointment_id, "cancel")

        assert result["routed"] == "AUTOMATED_ACTION"
        assert system.appointments[appt.appointment_id].status == "CANCELLED"

    def test_inbound_non_keyword_message_routes_to_staff_inbox(
            self, system, synthetic_patient, standard_visit_type, make_slot, now):
        """FR-402: a message with no recognized keyword routes to the staff inbox."""
        slot = make_slot(standard_visit_type, hours_from_now=72)
        appt = system.book_appointment(synthetic_patient.patient_id, slot.slot_id,
                                        standard_visit_type.visit_type_id, now=now)

        result = system.route_inbound_message(appt.appointment_id, "What time is my visit?")

        assert result["routed"] == "STAFF_INBOX"
        assert system.appointments[appt.appointment_id].status == "SCHEDULED"


# ===========================================================================
# L. RBAC, reporting & audit -- Section 2/7 NFRs, FR-503, FR-603
# ===========================================================================

class TestAuthorizationAndAudit:

    def test_export_report_allowed_for_authorized_role(self, system, billing_user):
        """TC-I-003: a role with export permission can export a report."""
        csv_data = system.export_report(actor=billing_user)
        assert "no_show_rate" in csv_data

    def test_export_report_denied_for_unauthorized_role(self, system, clinician_user):
        """TC-I-004: a role without export permission is denied."""
        with pytest.raises(ForbiddenError):
            system.export_report(actor=clinician_user)

    def test_export_report_is_audit_logged(self, system, billing_user):
        """TC-I-003 / FR-603: a successful export creates an audit entry."""
        system.export_report(actor=billing_user)
        assert any(e.action == "EXPORT" for e in system.audit_log)

    def test_audit_log_view_restricted_to_authorized_role(
            self, system, clinic_manager_user, system_admin_user):
        """TC-J-001: only an authorized role (system admin) can view the audit log."""
        with pytest.raises(ForbiddenError):
            system.get_audit_log(actor=clinic_manager_user)

        entries = system.get_audit_log(actor=system_admin_user)
        assert isinstance(entries, list)

    def test_view_patient_phi_denied_without_permission(
            self, system, synthetic_patient, clinic_manager_user):
        """TC-J-001: a role without 'view_patient_phi' cannot access PHI-relevant data."""
        with pytest.raises(ForbiddenError):
            system.get_patient_phi(synthetic_patient.patient_id, actor=clinic_manager_user)

    def test_view_patient_phi_allowed_for_clinician(
            self, system, synthetic_patient, clinician_user):
        """Positive counterpart: a clinician role can view patient PHI."""
        patient = system.get_patient_phi(synthetic_patient.patient_id, actor=clinician_user)
        assert patient.patient_id == synthetic_patient.patient_id

    def test_audit_entry_has_actor_and_timestamp_on_cancel(
            self, system, synthetic_patient, standard_visit_type, make_slot, now):
        """TC-I-005: audit entries capture actor, timestamp, and before/after values."""
        slot = make_slot(standard_visit_type, hours_from_now=72)
        appt = system.book_appointment(synthetic_patient.patient_id, slot.slot_id,
                                        standard_visit_type.visit_type_id, now=now)
        system.cancel_appointment(appt.appointment_id, reason_code="PATIENT_REQUEST", now=now)

        cancel_entries = [e for e in system.audit_log if e.action == "CANCEL"]
        assert len(cancel_entries) == 1
        entry = cancel_entries[0]
        assert entry.actor == synthetic_patient.patient_id
        assert entry.timestamp == now
        assert entry.before is not None and entry.after is not None
