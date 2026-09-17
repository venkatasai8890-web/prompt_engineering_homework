# Homework 2 — API Specifications
## Outpatient Patient Scheduling & Care System (OSCS) — ABC Health Care Company

Source: `ABC_Health_Care_Outpatient_Scheduling_PRD.pdf`, PRD v1.0, December 20, 2025.
APIs below are derived only from capabilities the PRD describes as system behavior (registration,
scheduling, waitlist, check-in, intake/consent, care plans/tasks, notifications, reporting, audit).
All endpoints assume TLS 1.2+ in transit and RBAC-enforced authorization (Section 7 NFRs; Section 2).

---

## 1. Patient Registration & Identity — FR-001

### 1.1 Register patient account
- **Method / Endpoint:** `POST /api/v1/patients/register`
- **Purpose:** Create a new patient account using email and/or phone; triggers OTP verification.
- **Request body:**
```json
{
  "email": "patient@example.com",
  "phone": "+15551234567",
  "password": "********"
}
```
- **Example response (202 Accepted):**
```json
{
  "patientId": "pat_8f2a1c",
  "status": "PENDING_OTP_VERIFICATION",
  "otpSentTo": "phone"
}
```
- **Status codes:** `202 Accepted` (OTP sent), `400 Bad Request` (missing/invalid fields), `409 Conflict` (account already exists), `429 Too Many Requests` (rate-limited).

### 1.2 Verify OTP
- **Method / Endpoint:** `POST /api/v1/patients/{patientId}/verify-otp`
- **Purpose:** Confirm the OTP to activate the account (FR-001).
- **Request body:** `{ "otp": "482913" }`
- **Example response (200 OK):** `{ "patientId": "pat_8f2a1c", "status": "ACTIVE" }`
- **Status codes:** `200 OK`, `400 Bad Request` (invalid OTP), `410 Gone` (OTP expired), `429 Too Many Requests`.

### 1.3 Patient login
- **Method / Endpoint:** `POST /api/v1/auth/login`
- **Purpose:** Authenticate a patient or staff user; login attempts are rate-limited and audited (FR-001).
- **Request body:** `{ "identifier": "patient@example.com", "password": "********" }`
- **Example response (200 OK):** `{ "accessToken": "eyJ...", "expiresIn": 3600 }`
- **Status codes:** `200 OK`, `401 Unauthorized` (bad credentials), `423 Locked` / `429 Too Many Requests` (rate-limited).

---

## 2. Patient Profile — FR-002

### 2.1 Get patient profile
- **Method / Endpoint:** `GET /api/v1/patients/{patientId}`
- **Purpose:** Retrieve demographics, contact info, language, communication preferences, emergency contact.
- **Example response (200 OK):**
```json
{
  "patientId": "pat_8f2a1c",
  "firstName": "Jane",
  "lastName": "Doe",
  "preferredLanguage": "en",
  "communicationPreferences": { "sms": true, "email": true },
  "emergencyContact": { "name": "John Doe", "phone": "+15559876543", "relationship": "spouse" }
}
```
- **Status codes:** `200 OK`, `403 Forbidden` (RBAC denial), `404 Not Found`.

### 2.2 Update patient profile
- **Method / Endpoint:** `PATCH /api/v1/patients/{patientId}`
- **Purpose:** Update demographics, contact info, preferences, or emergency contact (FR-002).
- **Request body:** `{ "preferredLanguage": "es", "emergencyContact": { "name": "John Doe", "phone": "+15559876543" } }`
- **Example response (200 OK):** Updated patient object (same shape as 2.1).
- **Status codes:** `200 OK`, `400 Bad Request`, `403 Forbidden`, `404 Not Found`.

---

## 3. Appointment Search & Booking — FR-003, FR-102, FR-103, FR-107

### 3.1 Search available slots
- **Method / Endpoint:** `GET /api/v1/appointments/availability`
- **Purpose:** Return eligible time slots for a visit type, supporting multi-location/cross-location search (FR-003, FR-102).
- **Query parameters:** `visitTypeId`, `locationId` (optional, omit for cross-location), `providerId` (optional), `startDate`, `endDate`.
- **Example response (200 OK):**
```json
{
  "slots": [
    { "slotId": "slot_991", "providerId": "prov_12", "locationId": "loc_02", "startTime": "2026-01-05T09:00:00Z", "durationMinutes": 30 }
  ]
}
```
- **Status codes:** `200 OK` (results in <2s per NFR), `400 Bad Request` (invalid params), `422 Unprocessable Entity` (visit type not eligible for search channel).

### 3.2 Book an appointment
- **Method / Endpoint:** `POST /api/v1/appointments`
- **Purpose:** Book a slot; instant for eligible visit types, else creates a "Requested" appointment pending approval (FR-003, FR-108).
- **Request body:**
```json
{
  "patientId": "pat_8f2a1c",
  "slotId": "slot_991",
  "visitTypeId": "vt_consult_01"
}
```
- **Example response (201 Created):**
```json
{
  "appointmentId": "appt_4471",
  "status": "SCHEDULED",
  "slotId": "slot_991",
  "confirmationSent": true
}
```
- **Status codes:** `201 Created`, `400 Bad Request`, `409 Conflict` (slot already booked / double-booking), `422 Unprocessable Entity` (eligibility constraint failed per FR-107, e.g. missing referral or new-patient restriction).

### 3.3 Get appointment
- **Method / Endpoint:** `GET /api/v1/appointments/{appointmentId}`
- **Purpose:** Retrieve current appointment details and lifecycle state (FR-108).
- **Example response (200 OK):** `{ "appointmentId": "appt_4471", "status": "CONFIRMED", "patientId": "pat_8f2a1c", "providerId": "prov_12", "startTime": "2026-01-05T09:00:00Z" }`
- **Status codes:** `200 OK`, `403 Forbidden`, `404 Not Found`.

---

## 4. Reschedule & Cancellation — FR-004, FR-105

### 4.1 Reschedule appointment
- **Method / Endpoint:** `PATCH /api/v1/appointments/{appointmentId}/reschedule`
- **Purpose:** Move an appointment to a new slot within the configured policy window (FR-004).
- **Request body:** `{ "newSlotId": "slot_995" }`
- **Example response (200 OK):** `{ "appointmentId": "appt_4471", "status": "SCHEDULED", "slotId": "slot_995" }`
- **Status codes:** `200 OK`, `403 Forbidden` (outside policy window), `409 Conflict` (new slot unavailable).

### 4.2 Cancel appointment
- **Method / Endpoint:** `PATCH /api/v1/appointments/{appointmentId}/cancel`
- **Purpose:** Cancel an appointment, capturing a structured reason and optional free text; may trigger waitlist offers (FR-004, FR-105).
- **Request body:** `{ "reasonCode": "SCHEDULE_CONFLICT", "reasonText": "Work conflict" }`
- **Example response (200 OK):** `{ "appointmentId": "appt_4471", "status": "CANCELLED", "waitlistTriggered": true }`
- **Status codes:** `200 OK`, `403 Forbidden` (outside policy window), `404 Not Found`.

### 4.3 Join waitlist
- **Method / Endpoint:** `POST /api/v1/waitlist`
- **Purpose:** Opt a patient into the waitlist with preferred windows and acceptable providers/locations (FR-105).
- **Request body:**
```json
{
  "patientId": "pat_8f2a1c",
  "visitTypeId": "vt_consult_01",
  "preferredWindows": [{ "start": "2026-01-05T08:00:00Z", "end": "2026-01-09T18:00:00Z" }],
  "acceptableProviderIds": ["prov_12", "prov_15"],
  "acceptableLocationIds": ["loc_02"]
}
```
- **Example response (201 Created):** `{ "waitlistEntryId": "wl_331", "status": "ACTIVE" }`
- **Status codes:** `201 Created`, `400 Bad Request`.

### 4.4 Respond to waitlist offer
- **Method / Endpoint:** `POST /api/v1/waitlist/{waitlistEntryId}/offers/{offerId}/respond`
- **Purpose:** Accept or decline a time-limited waitlist slot offer (FR-105).
- **Request body:** `{ "response": "ACCEPT" }`
- **Example response (200 OK):** `{ "offerId": "off_77", "status": "ACCEPTED", "appointmentId": "appt_4499" }`
- **Status codes:** `200 OK`, `410 Gone` (offer expired), `409 Conflict` (slot no longer available).

---

## 5. Resource & Overbooking — FR-104, FR-106

### 5.1 Book with overbooking override
- **Method / Endpoint:** `POST /api/v1/appointments/overbook`
- **Purpose:** Book beyond normal capacity where policy allows, requiring justification; result is audited and flagged (FR-106).
- **Request body:** `{ "patientId": "pat_8f2a1c", "slotId": "slot_991", "visitTypeId": "vt_consult_01", "justification": "Urgent same-day symptom escalation" }`
- **Example response (201 Created):** `{ "appointmentId": "appt_4512", "status": "SCHEDULED", "overbooked": true }`
- **Status codes:** `201 Created`, `400 Bad Request` (missing justification), `403 Forbidden` (overbooking not permitted for this provider/visit type/time), `409 Conflict` (resource conflict across provider/room/equipment per FR-104).

---

## 6. Intake, Consent & Check-in — FR-005, FR-201, FR-202, FR-203

### 6.1 Get intake status
- **Method / Endpoint:** `GET /api/v1/appointments/{appointmentId}/intake`
- **Purpose:** Retrieve completion status of required intake forms/consents (FR-005, FR-201).
- **Example response (200 OK):** `{ "appointmentId": "appt_4471", "items": [{ "formId": "form_hx_01", "status": "PENDING" }, { "formId": "consent_tele_01", "status": "SIGNED" }] }`
- **Status codes:** `200 OK`, `403 Forbidden`, `404 Not Found`.

### 6.2 Submit intake form response
- **Method / Endpoint:** `POST /api/v1/appointments/{appointmentId}/intake/{formId}/responses`
- **Purpose:** Submit patient answers to an intake questionnaire (FR-005).
- **Request body:** `{ "answers": { "q1": "No known allergies" } }`
- **Example response (201 Created):** `{ "formId": "form_hx_01", "status": "COMPLETED" }`
- **Status codes:** `201 Created`, `400 Bad Request`, `409 Conflict` (already submitted).

### 6.3 Sign consent document
- **Method / Endpoint:** `POST /api/v1/appointments/{appointmentId}/consents/{consentId}/sign`
- **Purpose:** Capture e-signature for a required consent; result is immutable and versioned (FR-005).
- **Request body:** `{ "signatureData": "base64-signature-blob", "signedAt": "2026-01-04T14:32:00Z" }`
- **Example response (201 Created):** `{ "consentId": "consent_tele_01", "status": "SIGNED", "version": 1 }`
- **Status codes:** `201 Created`, `409 Conflict` (already signed — immutable).

### 6.4 Check in patient
- **Method / Endpoint:** `POST /api/v1/appointments/{appointmentId}/check-in`
- **Purpose:** Perform front-desk or policy-gated mobile self check-in (FR-202); updates lifecycle state and status board (FR-108, FR-203).
- **Request body:** `{ "mode": "MOBILE_SELF", "geoLocation": { "lat": 37.77, "lng": -122.41 } }`
- **Example response (200 OK):** `{ "appointmentId": "appt_4471", "status": "CHECKED_IN" }`
- **Status codes:** `200 OK`, `403 Forbidden` (outside allowed time/geo-fence for mobile self check-in), `404 Not Found`.

### 6.5 Get clinic status board
- **Method / Endpoint:** `GET /api/v1/clinic-status-board`
- **Purpose:** Real-time view of patient flow, filterable by provider/location/visit type (FR-203).
- **Query parameters:** `locationId`, `providerId`, `visitTypeId` (all optional).
- **Example response (200 OK):**
```json
{
  "entries": [
    { "appointmentId": "appt_4471", "patientInitials": "J.D.", "status": "ARRIVED", "providerId": "prov_12" }
  ]
}
```
- **Status codes:** `200 OK` (updates reflected within 5s per NFR), `403 Forbidden`.

---

## 7. Care Plans & Tasks — FR-301, FR-302, FR-303

### 7.1 Create care plan
- **Method / Endpoint:** `POST /api/v1/encounters/{encounterId}/care-plans`
- **Purpose:** Create a care plan tied to an encounter with goals, interventions, tasks, and due dates (FR-301).
- **Request body:**
```json
{
  "goals": ["Improve blood pressure control"],
  "interventions": ["Dietary counseling"],
  "tasks": [{ "description": "Follow-up lab draw", "ownerType": "PATIENT", "dueDate": "2026-01-20" }]
}
```
- **Example response (201 Created):** `{ "carePlanId": "cp_221", "encounterId": "enc_990", "status": "ACTIVE" }`
- **Status codes:** `201 Created`, `400 Bad Request`, `403 Forbidden`.

### 7.2 Update task status
- **Method / Endpoint:** `PATCH /api/v1/tasks/{taskId}`
- **Purpose:** Update a task's owner, due date, priority, or status; overdue tasks escalate per policy (FR-302).
- **Request body:** `{ "status": "COMPLETED" }`
- **Example response (200 OK):** `{ "taskId": "task_5502", "status": "COMPLETED" }`
- **Status codes:** `200 OK`, `403 Forbidden`, `404 Not Found`.

### 7.3 Generate follow-up appointment suggestion
- **Method / Endpoint:** `POST /api/v1/care-plans/{carePlanId}/schedule-next`
- **Purpose:** Generate a follow-up appointment suggestion from a care plan task ("schedule next" workflow) (FR-303).
- **Request body:** `{ "taskId": "task_5502" }`
- **Example response (200 OK):** `{ "suggestedVisitTypeId": "vt_followup_01", "suggestedSlots": ["slot_1102", "slot_1109"] }`
- **Status codes:** `200 OK`, `404 Not Found`.

---

## 8. Notifications & Messaging — FR-401, FR-402

### 8.1 Get notification preferences
- **Method / Endpoint:** `GET /api/v1/patients/{patientId}/notification-preferences`
- **Purpose:** Retrieve opt-in/opt-out status per channel (FR-401).
- **Example response (200 OK):** `{ "sms": true, "email": false }`
- **Status codes:** `200 OK`, `403 Forbidden`.

### 8.2 Update notification preferences
- **Method / Endpoint:** `PATCH /api/v1/patients/{patientId}/notification-preferences`
- **Purpose:** Update opt-in/opt-out preferences, enforced on subsequent sends (FR-401).
- **Request body:** `{ "sms": false }`
- **Example response (200 OK):** `{ "sms": false, "email": false }`
- **Status codes:** `200 OK`, `400 Bad Request`.

### 8.3 Get notification delivery status
- **Method / Endpoint:** `GET /api/v1/notifications/{notificationId}`
- **Purpose:** Track delivery status of a sent notification (FR-401, FR-702).
- **Example response (200 OK):** `{ "notificationId": "notif_9001", "template": "REMINDER", "channel": "SMS", "status": "DELIVERED" }`
- **Status codes:** `200 OK`, `404 Not Found`.

### 8.4 Receive inbound patient message (webhook)
- **Method / Endpoint:** `POST /api/v1/messages/inbound`
- **Purpose:** Receive an inbound SMS/portal reply; applies keyword routing (e.g., "CANCEL") or routes to staff inbox (FR-402).
- **Request body:** `{ "fromPhone": "+15551234567", "body": "CANCEL", "channel": "SMS" }`
- **Example response (200 OK):** `{ "routed": "AUTOMATED_ACTION", "action": "CANCEL_APPOINTMENT", "appointmentId": "appt_4471" }`
- **Status codes:** `200 OK`, `400 Bad Request`, `422 Unprocessable Entity` (no matching appointment to act on).

---

## 9. Reporting & Audit — FR-501, FR-502, FR-503, FR-603

### 9.1 Get operational dashboard metrics
- **Method / Endpoint:** `GET /api/v1/reports/operational`
- **Purpose:** Retrieve no-show rate, late cancel rate, utilization, lead time, fill rate, waitlist conversion (FR-501).
- **Query parameters:** `locationId`, `providerId`, `dateRange`.
- **Example response (200 OK):** `{ "noShowRate": 0.08, "lateCancelRate": 0.05, "utilization": 0.82, "fillRate": 0.63 }`
- **Status codes:** `200 OK`, `403 Forbidden`.

### 9.2 Get clinical follow-through metrics
- **Method / Endpoint:** `GET /api/v1/reports/clinical-follow-through`
- **Purpose:** Retrieve task completion, follow-up adherence, referral completion rates, restricted by role (FR-502).
- **Example response (200 OK):** `{ "taskCompletionRate": 0.91, "followUpAdherence": 0.77, "referralCompletionRate": 0.68 }`
- **Status codes:** `200 OK`, `403 Forbidden` (role restriction on provider-level detail).

### 9.3 Export report as CSV
- **Method / Endpoint:** `GET /api/v1/reports/{reportType}/export`
- **Purpose:** Export a report as CSV with role-based restriction; export action is audit logged (FR-503).
- **Example response (200 OK):** CSV file stream, `Content-Type: text/csv`.
- **Status codes:** `200 OK`, `403 Forbidden` (role lacks export permission).

### 9.4 Query audit log
- **Method / Endpoint:** `GET /api/v1/audit-log`
- **Purpose:** Retrieve audit entries for appointments, patient demographics, care plans/tasks, or permission changes (FR-603).
- **Query parameters:** `entityType`, `entityId`, `dateRange`.
- **Example response (200 OK):**
```json
{
  "entries": [
    { "actor": "user_staff_44", "timestamp": "2026-01-04T10:15:00Z", "entityType": "APPOINTMENT", "action": "UPDATE", "before": { "status": "SCHEDULED" }, "after": { "status": "CANCELLED" }, "justification": null }
  ]
}
```
- **Status codes:** `200 OK`, `403 Forbidden` (restricted to authorized/admin roles).

---

## 10. EHR/EMR Integration — FR-701

### 10.1 Sync appointment to EHR
- **Method / Endpoint:** `POST /api/v1/integrations/ehr/appointments/sync`
- **Purpose:** Push/pull appointment data to/from the EHR/EMR via HL7 v2 or FHIR; failures are retried and alerted (FR-701, NFR Reliability).
- **Request body:** `{ "appointmentId": "appt_4471", "direction": "OUTBOUND" }`
- **Example response (202 Accepted):** `{ "syncJobId": "sync_338", "status": "QUEUED" }`
- **Status codes:** `202 Accepted`, `502 Bad Gateway` / `503 Service Unavailable` (EHR unreachable — routed to retry queue), `409 Conflict` (conflicting source-of-truth data).
