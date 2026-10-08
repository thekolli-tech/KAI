# PostgreSQL

`migrations/001_initial.sql` is the schema. Apply it once as a role that can
create tables. The API then sets the session role to `kai_app` and sets
`kai.organization_id` and `kai.user_id` from the authenticated principal.
Do not point `DATABASE_URL` at a superuser without that role change: superusers
bypass row level security.
