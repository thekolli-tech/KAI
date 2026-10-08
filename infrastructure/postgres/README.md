# PostgreSQL

`migrations/001_initial.sql` is the Phase 1 schema. The API does not apply it
and does not open a connection. When persistence starts, apply it as `kai_app`,
not as a superuser.
