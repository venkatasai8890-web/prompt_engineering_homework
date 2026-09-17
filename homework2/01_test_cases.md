# Homework 2 — Test Cases
## Outpatient Patient Scheduling & Care System (OSCS) — ABC Health Care Company

Source: `ABC_Health_Care_Outpatient_Scheduling_PRD.pdf`, PRD v1.0, December 20, 2025.
Every test case below is traceable to a specific Functional Requirement (FR-###) or Non-Functional
Requirement (NFR) in the PRD. No requirement outside the document is assumed.

---

## A. Patient Registration, Identity & Profile (FR-001, FR-002)

| Test Case ID | Scenario | Preconditions | Test Steps | Expected Result |
|---|---|---|---|---|
| TC-A-001 | Patient successfully registers with email | Patient does not have an existing account | 1. Navigate to registration. 2. Enter valid email and/or phone. 3. Submit. 4. Enter OTP received. | Account is created; OTP verification succeeds; authentication event is recorded in the audit log (FR-001). |
| TC-A-002 | Patient registration fails with invalid OTP | Patient has started registration and an OTP was sent | 1. Enter valid email/phone. 2. Enter an incorrect OTP. | Registration is rejected; account is not created; failed attempt is logged (FR-001). |
| TC-A-003 (Negative) | Repeated failed login attempts are rate-limited | Patient has an existing account | 1. Attempt login with wrong credentials multiple times in succession. | After the configured threshold, further attempts are blocked/rate-limited; each attempt is audited (FR-001). |
| TC-A-004 | Patient updates profile information | Patient is logged in | 1. Open profile. 2. Update demographics, contact info, preferred language, and communication preferences. 3. Save. | Profile updates are saved and reflected on next view (FR-002). |
| TC-A-005 | Patient adds emergency contact | Patient is logged in | 1. Open profile. 2. Add emergency contact name/relationship/phone. 3. Save. | Emergency contact is stored against the patient profile (FR-002). |

---

## B. Appointment Search & Self-Scheduling (FR-003, FR-102, FR-103, FR-107)

| Test Case ID | Scenario | Preconditions | Test Steps | Expected Result |
|---|---|---|---|---|
| TC-B-001 (Positive) | Patient books an instant-booking-eligible visit type | Visit type is configured for patient self-scheduling; eligible slots exist | 1. Search by visit type, location, provider preference, time window. 2. Select an available slot. 3. Confirm booking. | Appointment is booked instantly; confirmation is sent; only eligible slots were displayed (FR-003). |
| TC-B-002 | Patient requests a visit type requiring approval | Visit type is configured as "request-and-approve" | 1. Search and select a slot for that visit type. 2. Submit request. | Appointment enters "Requested" state pending staff approval, not instantly confirmed (FR-003, FR-108). |
| TC-B-003 (Negative) | Double-booking is prevented | A slot is already booked for a provider/resource | 1. Two different patients/staff attempt to book the same slot concurrently. | Second booking attempt is blocked unless clinic policy explicitly allows overlap; conflict is detected (FR-003, FR-104). |
| TC-B-004 (Validation) | Booking blocked when eligibility constraints fail | Visit type requires referral, and patient has none on file | 1. Attempt to book the visit type without a referral. | Booking is blocked or routed to a request-and-review workflow, per configured policy (FR-107). |
| TC-B-005 (Validation) | New-patient vs established-patient rule enforced | Visit type is restricted to established patients only | 1. A new patient attempts to book that visit type. | System blocks booking or routes to review, consistent with configured constraint (FR-107). |
| TC-B-006 | Cross-location availability search | Multiple clinic locations are configured with distinct hours/resources | 1. Search availability across locations for a visit type. | Results include eligible slots from all searched locations, respecting each location's hours (FR-102). |
| TC-B-007 | Staff-only visit type is not shown to patients | Visit type is configured as staff-only | 1. Patient searches for appointments including this visit type. | Visit type does not appear in patient self-scheduling search results (FR-103). |

---

## C. Reschedule & Cancellation (FR-004, FR-105)

| Test Case ID | Scenario | Preconditions | Test Steps | Expected Result |
|---|---|---|---|---|
| TC-C-001 (Positive) | Patient reschedules within policy window | Appointment exists; current time is within the configured reschedule window | 1. Open appointment. 2. Choose "Reschedule." 3. Select a new eligible slot. 4. Confirm. | Original slot is released, new slot is booked, confirmation is sent (FR-004). |
| TC-C-002 (Negative) | Reschedule blocked outside policy window | Appointment exists; current time is outside the configured reschedule window | 1. Attempt to reschedule. | System blocks the self-service reschedule per policy window (FR-004). |
| TC-C-003 (Cancellation) | Patient cancels an appointment with a reason | Appointment exists and is cancellable | 1. Open appointment. 2. Choose "Cancel." 3. Select a structured cancellation reason; optionally add free text. 4. Confirm. | Appointment status becomes "Cancelled"; reason is stored; transition is audited (FR-004, FR-108). |
| TC-C-004 | Cancellation triggers waitlist offer | A patient is waitlisted for the same provider/location/time window; waitlist is enabled | 1. Cancel an appointment matching a waitlisted patient's preferences. | Waitlist workflow is triggered; an offer is sent in priority order (FR-004, FR-105). |
| TC-C-005 (Negative) | Waitlist offer expires without response | Waitlist offer has been sent to a patient | 1. Do not respond to the offer before the configured expiry time. | Offer expires; slot is released back to general availability (FR-105). |
| TC-C-006 | Waitlist offer accepted before expiry | Waitlist offer has been sent to a patient | 1. Accept the offer before it expires. | Slot is booked to the accepting patient; offer is closed (FR-105). |

---

## D. Provider Calendars, Resources & Overbooking (FR-101, FR-104, FR-106)

| Test Case ID | Scenario | Preconditions | Test Steps | Expected Result |
|---|---|---|---|---|
| TC-D-001 | Provider schedule template updated with future effective date | Provider has a published schedule | 1. Staff updates the working-hours template with a future effective date. | Existing published appointments before the effective date are not broken; new template applies from the effective date forward (FR-101). |
| TC-D-002 (Negative) | Resource conflict is detected | A room/equipment resource is already reserved for a given time | 1. Attempt to book another appointment requiring the same resource at an overlapping time. | Conflict is detected and booking is blocked or flagged (FR-104). |
| TC-D-003 (Positive) | Staff books an overbooked slot with justification | Overbooking policy is enabled for the provider/visit type/time-of-day | 1. Staff attempts to book beyond normal capacity. 2. Enter a required justification. 3. Confirm. | Appointment is booked, visually flagged as overbooked, and the action is audited (FR-106). |
| TC-D-004 (Validation) | Overbooking without justification is rejected | Overbooking policy is enabled | 1. Attempt to book beyond capacity without entering a justification. | System rejects/blocks the booking until justification is provided (FR-106). |
| TC-D-005 (Negative) | Overbooking rejected where policy disallows it | Overbooking policy is disabled for the provider/visit type/time-of-day | 1. Attempt to book beyond capacity. | Booking is blocked entirely; no overbooking option is offered (FR-106). |

---

## E. Appointment Lifecycle States (FR-108)

| Test Case ID | Scenario | Preconditions | Test Steps | Expected Result |
|---|---|---|---|---|
| TC-E-001 (Positive) | Valid state transition sequence | Appointment exists in "Scheduled" state | 1. Transition through Confirmed → Checked-in → In-room → Completed as the visit progresses. | Each transition succeeds and is recorded in the audit log with actor and timestamp (FR-108, FR-603). |
| TC-E-002 (Negative) | Invalid state transition is rejected | Appointment exists in "Requested" state | 1. Attempt to transition directly to "Completed" without intermediate states. | Invalid transition is rejected; state remains unchanged; rejected attempt may be logged (FR-108). |
| TC-E-003 | No-show is recorded | Appointment time has passed with no check-in | 1. Mark the appointment as "No-show" per clinic process. | State transitions to "No-show"; transition is audited (FR-108, workflow exceptions section). |

---

## F. Intake, Consents & Check-in (FR-005, FR-201, FR-202, FR-203)

| Test Case ID | Scenario | Preconditions | Test Steps | Expected Result |
|---|---|---|---|---|
| TC-F-001 (Positive) | Patient completes intake form and e-signs consent | Appointment is booked; intake form is pending | 1. Open pending intake form. 2. Complete questionnaire. 3. E-sign required consent. 4. Submit. | Form and signed consent are saved; document becomes immutable and versioned; completion status is visible to staff (FR-005). |
| TC-F-002 (Negative) | Signed consent cannot be edited after signature | Consent has already been signed | 1. Attempt to modify a previously signed consent document. | Edit is rejected; document remains immutable; a new version would be required instead (FR-005). |
| TC-F-003 | Reminder sent for incomplete intake | Appointment exists; intake items are incomplete as visit date approaches | 1. Wait for/trigger the automated reminder process. | Reminder notification is sent to the patient for the missing intake items (FR-201). |
| TC-F-004 | Staff views missing intake items | Patient has incomplete intake items for an upcoming appointment | 1. Staff opens the appointment/patient record. | Staff can see which specific intake items are missing (FR-201). |
| TC-F-005 (Positive) | Front-desk check-in | Patient has arrived for an appointment | 1. Staff performs front-desk check-in for the appointment. | Appointment state updates to "Checked-in"; status board reflects "arrived" (FR-202, FR-203, FR-108). |
| TC-F-006 (Positive) | Mobile self check-in within policy window | Mobile check-in is enabled; patient is within the allowed time (and geo-fence, if configured) | 1. Patient opens portal/app. 2. Initiates self check-in. | Check-in succeeds; appointment state updates accordingly (FR-202). |
| TC-F-007 (Negative) | Mobile self check-in blocked outside allowed window/geo-fence | Mobile check-in is policy-gated by time and geo-fence | 1. Patient attempts self check-in outside the allowed time window or geo-fence. | Self check-in is blocked; patient is directed to front desk or alternative process (FR-202). |
| TC-F-008 | Clinic status board reflects patient flow in real time | Multiple patients are at various stages (arrived, waiting, roomed, completed) | 1. Open the clinic status board. 2. Filter by provider, location, and visit type. | Board displays accurate real-time patient flow and filters correctly; updates within 5 seconds under normal load (FR-203, NFR performance). |

---

## G. Care Plans & Task Management (FR-301, FR-302, FR-303)

| Test Case ID | Scenario | Preconditions | Test Steps | Expected Result |
|---|---|---|---|---|
| TC-G-001 (Positive) | Clinician creates a care plan tied to an encounter | Encounter/visit has occurred | 1. Clinician opens the encounter. 2. Creates a care plan with goals, interventions, tasks, and due dates. | Care plan is saved and linked to the encounter (FR-301). |
| TC-G-002 | Task assigned to a patient | Care plan exists with a task | 1. Assign a task to the patient with owner, due date, priority, status. | Task appears with correct owner/due date/priority/status (FR-302). |
| TC-G-003 (Negative) | Overdue task escalates per policy | Task due date has passed and task is incomplete | 1. Allow the task to go overdue. | Escalation occurs according to configured policy; reminder is sent (FR-302). |
| TC-G-004 (Positive) | "Schedule next" generates a follow-up appointment suggestion | Care plan contains a task implying a follow-up visit | 1. From visit documentation, select "schedule next." | System generates a follow-up appointment suggestion based on the care plan task (FR-303). |

---

## H. Notifications & Messaging (FR-401, FR-402)

| Test Case ID | Scenario | Preconditions | Test Steps | Expected Result |
|---|---|---|---|---|
| TC-H-001 (Positive) | Confirmation notification sent on booking | Patient has a valid, non-opted-out communication preference | 1. Book an appointment. | Confirmation SMS/email is sent; delivery status is tracked (FR-401). |
| TC-H-002 | Reminder sent at configured timing | Appointment is booked; reminder timing is configured | 1. Wait until the configured reminder time before the appointment. | Reminder notification is sent per template and timing configuration (FR-401). |
| TC-H-003 (Negative) | Opted-out patient does not receive notifications | Patient has opted out of SMS/email communications | 1. Trigger a notification event (e.g., booking confirmation) for this patient. | No notification is sent to the opted-out channel; preference is enforced (FR-401). |
| TC-H-004 (Positive) | Patient replies "CANCEL" via SMS | Patient has an upcoming appointment and two-way messaging is enabled | 1. Patient sends "CANCEL" via SMS reply. | Keyword routing triggers the automated cancellation action (or routes to staff inbox per configuration) (FR-402). |
| TC-H-005 | PHI-containing message is stored securely and audited | Two-way messaging is enabled | 1. Exchange a message containing PHI between patient and staff. | Message is stored securely; access/creation is audit logged (FR-402). |

---

## I. Reporting, Export & Audit (FR-501, FR-502, FR-503, FR-603)

| Test Case ID | Scenario | Preconditions | Test Steps | Expected Result |
|---|---|---|---|---|
| TC-I-001 | Operational dashboard displays no-show and utilization metrics | Historical appointment data exists | 1. Open the operational dashboard. | No-show rate, late cancel rate, utilization, lead time, fill rate, and waitlist conversion are displayed (FR-501). |
| TC-I-002 | Clinical follow-through dashboard respects role restrictions | User has a role without access to provider-level detail | 1. Attempt to view provider-level clinical follow-through data. | View is restricted per role; only permitted aggregation level is shown (FR-502). |
| TC-I-003 (Positive) | Authorized user exports CSV | User has export permission | 1. Request CSV export of a report. | Export succeeds; export action is audit logged (FR-503). |
| TC-I-004 (Negative) | Unauthorized user is blocked from CSV export | User lacks export permission | 1. Attempt to export a report. | Export request is denied (FR-503). |
| TC-I-005 (Validation) | Audit log captures before/after values on appointment edit | Appointment exists | 1. Staff edits an appointment field (e.g., time). 2. Save. | Audit entry is created with actor, timestamp, and before/after values (FR-603). |
| TC-I-006 | Justification captured where required | Action requires justification (e.g., overbooking, or a permission-sensitive change) | 1. Perform the action without entering a justification. | System requires justification before the action completes; once entered, it is stored with the audit entry (FR-603). |

---

## J. Access Control & Security (RBAC, Section 2, Section 7 NFRs)

| Test Case ID | Scenario | Preconditions | Test Steps | Expected Result |
|---|---|---|---|---|
| TC-J-001 (Negative) | User without permission cannot access PHI-relevant screen | User's role does not include the required permission | 1. Attempt to open a patient record or PHI-relevant screen/action. | Access is denied per least-privilege RBAC (Section 2). |
| TC-J-002 | PHI-relevant action is audit logged | User has permission to perform a PHI-relevant action | 1. Perform the action (e.g., view/update patient demographics). | Action is recorded in the immutable audit log (Section 2, FR-603). |
| TC-J-003 | Data in transit is encrypted | System is deployed per NFRs | 1. Inspect network traffic for a client-server request. | Traffic uses TLS 1.2+ (NFR — Security and privacy). |
| TC-J-004 | Session times out per configuration | Staff user is logged in; session timeout is configured | 1. Leave the session idle beyond the configured timeout. | Session is invalidated; user must re-authenticate (NFR — Security and privacy). |

---

## K. Performance & Reliability (Section 7 NFRs)

| Test Case ID | Scenario | Preconditions | Test Steps | Expected Result |
|---|---|---|---|---|
| TC-K-001 | Availability search performance | Typical clinic data volume is loaded | 1. Perform an availability search. | Results return in under 2 seconds (NFR — Performance). |
| TC-K-002 | Status board refresh performance | Normal system load | 1. Change a patient's status (e.g., check-in). 2. Observe the status board. | Board reflects the update within 5 seconds (NFR — Performance). |
| TC-K-003 (Negative) | Integration failure triggers retry/alert | EHR/EMR or messaging integration is unreachable | 1. Simulate an integration outage during a sync/send operation. | Failure is handled via a retry queue; an operational alert is raised (NFR — Reliability). |
