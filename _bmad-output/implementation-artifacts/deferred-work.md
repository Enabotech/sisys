# Deferred Work

## Deferred from: code review of story-1-10-unified-audit-log (2026-05-07)

### Transaction Outbox Pattern Not Implemented
**Detail:** AuditServiceImpl.record() directly calls event_publisher.publish() instead of writing to an outbox table within the same transaction. AuditOutboxModel exists but is not used.
**AC Violated:** AC-1 (Audit Logging)
**Resolution:** Deferred — requires significant architectural change, planned for Story 1.18a

### Audit API Route Handler Not Implemented
**Detail:** OpenAPI defines endpoints at /audit/* but no route handler file found at src/interfaces/api/audit.py. API endpoints are defined but no controller implementation exists.
**AC Violated:** AC-2, AC-3, AC-4
**Resolution:** Deferred — requires creating new file, planned for future story

### WORM Manager Not Called During Archive
**Detail:** AuditServiceImpl.archive() only updates the archived flag in PostgreSQL but never calls WORMManager.archive_object() or WORMManager.enable_worm_lock(). Spec requires "归档至 MinIO WORM 存储".
**AC Violated:** AC-4 (WORM Archival)
**Resolution:** Deferred — requires architectural changes, planned for Story 1.18a
