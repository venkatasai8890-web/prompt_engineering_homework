# Homework 2 — User Stories & Acceptance Criteria
## Outpatient Patient Scheduling & Care System (OSCS) — ABC Health Care Company

Source: `ABC_Health_Care_Outpatient_Scheduling_PRD.pdf`, PRD v1.0, December 20, 2025.
Format: "As a [user], I want [feature], so that [benefit]." Each story lists acceptance criteria
derived directly from the referenced Functional Requirement (FR-###).

---

## Patient Portal and Access

### US-01 — Account registration
**As a** patient, **I want** to create an account with my email and/or phone, **so that** I can access the portal to manage my care.
- Acceptance Criteria (FR-001):
  1. Given a new user, when they register with email and/or phone, an account is created.
  2. OTP verification is required to activate/confirm the account.
  3. Repeated failed login attempts are rate-limited.
  4. All authentication events (success and failure) are audit logged.

### US-02 — Manage profile
**As a** patient, **I want** to manage my demographics, contact info, language, and communication preferences, **so that** the clinic can reach and treat me correctly.
- Acceptance Criteria (FR-002):
  1. Patient can view and edit demographics, contact info, preferred language, and communication preferences.
  2. Patient can add and update emergency contact information.
  3. Changes are saved and reflected immediately on the profile.

### US-03 — Self-schedule an appointment
**As a** patient, **I want** to search and book an available appointment myself, **so that** I don't have to call the clinic for eligible visit types.
- Acceptance Criteria (FR-003):
  1. Patient can search by visit type, location, provider preference, and time window.
  2. Only eligible time slots are displayed to the patient.
  3. Instant booking is supported for eligible visit types; other visit types use a request-and-approve flow.
  4. Double-booking is prevented unless explicitly allowed by clinic policy.

### US-04 — Reschedule or cancel an appointment
**As a** patient, **I want** to reschedule or cancel my appointment within the allowed policy window, **so that** I can manage changes to my availability without calling staff.
- Acceptance Criteria (FR-004):
  1. Reschedule/cancel self-service is available only within the configured policy window.
  2. A cancellation reason is captured from a structured list, with optional free text.
  3. When a cancellation opens a slot, the waitlist workflow is triggered if enabled.

### US-05 — Complete intake forms and consents
**As a** patient, **I want** to complete intake forms, questionnaires, and consents digitally before my visit, **so that** my check-in is faster and my information is up to date.
- Acceptance Criteria (FR-005):
  1. Patient can complete intake forms and questionnaires digitally.
  2. Patient can e-sign required consent documents.
  3. Once signed, documents are immutable and versioned.
  4. Completion status of forms/consents is visible to staff.

### US-06 — Join a waitlist
**As a** patient, **I want** to opt into a waitlist for my preferred time window and providers/locations, **so that** I can get an earlier appointment if a slot opens up.
- Acceptance Criteria (FR-105):
  1. Patient can specify preferred time windows and acceptable providers/locations for the waitlist.
  2. When a matching slot opens, the patient receives an offer in priority order.
  3. The offer expires after a configurable time; if not accepted, the slot returns to general availability.

### US-07 — Receive appointment notifications
**As a** patient, **I want** to receive confirmations, reminders, and other appointment-related notifications, **so that** I don't miss my visit or important updates.
- Acceptance Criteria (FR-401):
  1. Notifications are sent via SMS and/or email for confirmation, reminders, intake pending, cancellation/reschedule, waitlist offers, and post-visit instructions.
  2. Reminder timing is configurable.
  3. Patient opt-in/opt-out preferences are stored and enforced.
  4. Delivery status of each notification is tracked.

### US-08 — Reply to messages
**As a** patient, **I want** to reply to SMS or portal messages (e.g., to cancel using a keyword), **so that** I can take quick action without logging into the portal.
- Acceptance Criteria (FR-402):
  1. Patient can reply to SMS or send a portal message.
  2. Keyword routing (e.g., "CANCEL") triggers the corresponding automated action or routes to the staff inbox.
  3. Messages containing PHI are stored securely and are audit logged.

---

## Front Desk / Scheduling Staff

### US-09 — Book and manage appointments on behalf of patients
**As a** front desk / scheduling staff member, **I want** to search availability and book, reschedule, or cancel appointments for patients, **so that** I can support patients who call or arrive in person.
- Acceptance Criteria (FR-003, FR-004, FR-108):
  1. Staff can search eligible slots by provider, location, visit type, and time window, including cross-location search.
  2. Staff can book, reschedule, and cancel appointments, capturing a cancellation reason when applicable.
  3. Appointment state transitions (e.g., Scheduled → Confirmed → Cancelled) are validated and audited.

### US-10 — Use overbooking with justification
**As a** front desk / scheduling staff member, **I want** to overbook a slot when clinic policy allows it, **so that** I can accommodate urgent patient needs without violating clinic rules.
- Acceptance Criteria (FR-106):
  1. Overbooking is only available where policy permits it (by provider, visit type, time-of-day).
  2. Staff must enter a justification to complete an overbooked booking.
  3. Overbooked appointments are visually flagged, and the action is audited.

### US-11 — Check patients in
**As a** front desk staff member, **I want** to check patients in on arrival, **so that** the clinic's status board and clinical team know the patient is ready.
- Acceptance Criteria (FR-202, FR-203, FR-108):
  1. Staff can perform front-desk check-in, optionally capturing insurance card and ID images.
  2. Appointment state updates to "Checked-in."
  3. The status board reflects the patient's arrival in real time.

### US-12 — View missing intake items
**As a** front desk / scheduling staff member, **I want** to see which intake items are missing for a patient's upcoming appointment, **so that** I can help them complete intake before or at check-in.
- Acceptance Criteria (FR-201):
  1. Staff can view a list of missing intake items per patient/appointment.
  2. Automated reminders are sent to patients for incomplete intake items.

---

## Clinician (MD/DO/NP/PA)

### US-13 — View and manage the clinic status board
**As a** clinician, **I want** to see a real-time view of patient flow (arrived, waiting, roomed, completed), **so that** I can manage my day efficiently.
- Acceptance Criteria (FR-203):
  1. Status board shows real-time patient flow states.
  2. Board can be filtered by provider, location, and visit type.
  3. Board updates within 5 seconds under normal load.

### US-14 — Create a care plan after a visit
**As a** clinician, **I want** to create a care plan tied to the encounter, **so that** the patient's goals, interventions, and follow-up tasks are documented and tracked.
- Acceptance Criteria (FR-301):
  1. Care plan can be created and linked to a specific encounter.
  2. Care plan includes goals, interventions, tasks, and due dates.

### US-15 — Schedule the next appointment from documentation
**As a** clinician, **I want** to trigger a "schedule next" workflow from visit documentation, **so that** follow-up visits are booked without a separate manual process.
- Acceptance Criteria (FR-303):
  1. Follow-up appointment suggestions are generated based on care plan tasks.
  2. A "schedule next" action is available directly from visit documentation.

---

## Nurse / Care Coordinator

### US-16 — Assign and track follow-up tasks
**As a** nurse / care coordinator, **I want** to assign tasks to patients or staff with an owner, due date, and priority, **so that** follow-up care items are completed on time.
- Acceptance Criteria (FR-302):
  1. Tasks can be assigned to a patient or staff member, with owner, due date, priority, and status fields.
  2. Overdue tasks escalate according to configured policy.
  3. Reminders are sent for tasks as configured.

### US-17 — Coordinate with the care team internally
**As a** nurse / care coordinator, **I want** to message other care team members with @mentions and templates, **so that** I can coordinate patient follow-through efficiently.
- Acceptance Criteria (FR-304):
  1. Internal care team messaging supports @mentions and message templates.
  2. Internal messaging is distinct from patient-facing communication, which goes through the communication module.

---

## Clinic Manager

### US-18 — Monitor operational performance
**As a** clinic manager, **I want** to view dashboards for no-show rate, utilization, lead time, fill rate, and waitlist conversion, **so that** I can identify and address scheduling inefficiencies.
- Acceptance Criteria (FR-501):
  1. Dashboard displays no-show rate, late cancel rate, utilization, lead time, fill rate, and waitlist conversion.
  2. Staff productivity metrics (appointments booked, requests handled) are available where applicable.

### US-19 — Monitor clinical follow-through
**As a** clinic manager, **I want** to view task completion, follow-up adherence, and referral completion rates, **so that** I can ensure patients are receiving complete care.
- Acceptance Criteria (FR-502):
  1. Metrics include task completion rate, follow-up adherence, and referral completion.
  2. Views are available at clinic and provider level, respecting role-based restrictions.

### US-20 — Configure overbooking and scheduling policy
**As a** clinic manager, **I want** to configure overbooking policies by provider, visit type, and time-of-day, **so that** capacity rules match clinic operating needs.
- Acceptance Criteria (FR-106, FR-601):
  1. Overbooking policy is configurable at the provider / visit-type / time-of-day level.
  2. Clinic setup allows managing locations, hours, holidays, rooms, equipment, providers, roles, specialties, visit types, intake requirements, and policy rules.

---

## System Admin / IT

### US-21 — Manage clinic configuration
**As a** system admin, **I want** to configure locations, providers, visit types, and policy rules, **so that** the scheduling system reflects how the clinic actually operates.
- Acceptance Criteria (FR-601, FR-602):
  1. Admin can manage locations, hours, holidays, rooms, and equipment.
  2. Admin can manage providers, roles, specialties, visit types, intake requirements, and policy rules.
  3. Appointment and form templates support versioning and effective dates.

### US-22 — Review audit logs
**As a** system admin, **I want** to review audit logs for appointments, patient demographics, care plans/tasks, and permission changes, **so that** I can support compliance and investigate issues.
- Acceptance Criteria (FR-603):
  1. Audit logs track create/update/delete actions on appointments, patient demographics, care plans/tasks, and permissions.
  2. Each audit entry includes actor, timestamp, and before/after values.
  3. Justification is captured when required (e.g., overbooking).

### US-23 — Enforce role-based access control
**As a** system admin, **I want** to assign least-privilege, role-based permissions to users, **so that** PHI is only accessible to authorized personnel.
- Acceptance Criteria (Section 2, Section 7 NFRs):
  1. RBAC with least-privilege permissions is enforced across the system.
  2. Separation of duties is applied where appropriate.
  3. All PHI-relevant actions are audit logged.

---

## Billing Staff (optional for MVP)

### US-24 — Export reports for billing-relevant analysis
**As a** billing staff member, **I want** to export scheduling and utilization reports as CSV, **so that** I can analyze data relevant to billing operations.
- Acceptance Criteria (FR-503):
  1. CSV export is available with role-based restrictions.
  2. Export actions are audit logged.
  3. Read-only API access for BI tooling may be available (optional, per PRD).
