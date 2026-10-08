-- KAI schema.
-- Apply this file before starting the API with DATABASE_URL set.
-- Tenant queries run as kai_app. The connection user must be able to SET ROLE kai_app.
--
-- Tenancy: the application role is kai_app, not the database owner and not a superuser.
-- Before a request touches tenant data, the server sets:
--   SET LOCAL kai.organization_id = '<membership organization uuid>';
--   SET LOCAL kai.user_id = '<authenticated user uuid>';
-- Those values come from the membership record, never from a client header alone.
-- Superusers bypass row level security. Do not run the application as one.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kai_app') THEN
    CREATE ROLE kai_app NOLOGIN;
  END IF;
END
$$;

CREATE OR REPLACE FUNCTION kai_set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION kai_current_org()
RETURNS uuid
LANGUAGE sql
STABLE
AS $$
  SELECT NULLIF(current_setting('kai.organization_id', true), '')::uuid
$$;

CREATE OR REPLACE FUNCTION kai_current_user()
RETURNS uuid
LANGUAGE sql
STABLE
AS $$
  SELECT NULLIF(current_setting('kai.user_id', true), '')::uuid
$$;

CREATE TYPE membership_role AS ENUM ('owner', 'admin', 'member');
CREATE TYPE message_role AS ENUM ('user', 'assistant', 'system', 'tool');
CREATE TYPE memory_scope AS ENUM ('short_term', 'long_term', 'project');

CREATE TABLE organizations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL CHECK (char_length(name) > 0),
  slug text NOT NULL UNIQUE CHECK (char_length(slug) > 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email text NOT NULL UNIQUE CHECK (char_length(email) > 3),
  display_name text NOT NULL CHECK (char_length(display_name) > 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE memberships (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations (id),
  user_id uuid NOT NULL REFERENCES users (id),
  role membership_role NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, user_id)
);

CREATE TABLE projects (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations (id),
  name text NOT NULL CHECK (char_length(name) > 0),
  description text NOT NULL DEFAULT '',
  created_by uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (id, organization_id),
  FOREIGN KEY (organization_id, created_by)
    REFERENCES memberships (organization_id, user_id)
);

CREATE TABLE conversations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations (id),
  project_id uuid,
  title text NOT NULL DEFAULT '',
  created_by uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (id, organization_id),
  FOREIGN KEY (organization_id, created_by)
    REFERENCES memberships (organization_id, user_id),
  FOREIGN KEY (project_id, organization_id)
    REFERENCES projects (id, organization_id)
);

CREATE TABLE messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  conversation_id uuid NOT NULL,
  role message_role NOT NULL,
  content text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (conversation_id, organization_id)
    REFERENCES conversations (id, organization_id) ON DELETE CASCADE
);

CREATE TABLE files (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations (id),
  project_id uuid,
  conversation_id uuid,
  object_key text NOT NULL CHECK (char_length(object_key) > 0),
  filename text NOT NULL CHECK (char_length(filename) > 0),
  media_type text NOT NULL CHECK (char_length(media_type) > 0),
  byte_size bigint NOT NULL CHECK (byte_size >= 0),
  created_by uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (id, organization_id),
  FOREIGN KEY (organization_id, created_by)
    REFERENCES memberships (organization_id, user_id),
  FOREIGN KEY (project_id, organization_id)
    REFERENCES projects (id, organization_id),
  FOREIGN KEY (conversation_id, organization_id)
    REFERENCES conversations (id, organization_id)
);

CREATE TABLE memories (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations (id),
  user_id uuid NOT NULL,
  project_id uuid,
  scope memory_scope NOT NULL,
  content text NOT NULL CHECK (char_length(content) > 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  FOREIGN KEY (organization_id, user_id)
    REFERENCES memberships (organization_id, user_id),
  FOREIGN KEY (project_id, organization_id)
    REFERENCES projects (id, organization_id)
);

CREATE TABLE agents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations (id),
  name text NOT NULL CHECK (char_length(name) > 0),
  description text NOT NULL DEFAULT '',
  capabilities jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, name)
);

CREATE TABLE tools (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations (id),
  name text NOT NULL CHECK (char_length(name) > 0),
  description text NOT NULL DEFAULT '',
  permissions jsonb NOT NULL DEFAULT '[]'::jsonb,
  enabled boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, name)
);

CREATE TABLE usage_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  user_id uuid NOT NULL,
  kind text NOT NULL CHECK (char_length(kind) > 0),
  units integer NOT NULL CHECK (units >= 0),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (organization_id, user_id)
    REFERENCES memberships (organization_id, user_id)
);

CREATE TABLE audit_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  actor_user_id uuid,
  action text NOT NULL CHECK (char_length(action) > 0),
  resource_type text NOT NULL CHECK (char_length(resource_type) > 0),
  resource_id uuid,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (organization_id, actor_user_id)
    REFERENCES memberships (organization_id, user_id)
);

CREATE INDEX conversations_org_updated_idx
  ON conversations (organization_id, updated_at DESC);
CREATE INDEX messages_conversation_idx
  ON messages (organization_id, conversation_id, created_at);
CREATE INDEX projects_org_idx ON projects (organization_id);
CREATE INDEX files_org_idx ON files (organization_id);
CREATE INDEX memories_active_idx
  ON memories (organization_id, user_id, scope)
  WHERE deleted_at IS NULL;
CREATE INDEX usage_events_org_idx ON usage_events (organization_id, created_at);
CREATE INDEX audit_logs_org_idx ON audit_logs (organization_id, created_at);
CREATE INDEX memberships_user_idx ON memberships (user_id);

CREATE TRIGGER organizations_updated_at
  BEFORE UPDATE ON organizations
  FOR EACH ROW EXECUTE FUNCTION kai_set_updated_at();
CREATE TRIGGER users_updated_at
  BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION kai_set_updated_at();
CREATE TRIGGER projects_updated_at
  BEFORE UPDATE ON projects
  FOR EACH ROW EXECUTE FUNCTION kai_set_updated_at();
CREATE TRIGGER conversations_updated_at
  BEFORE UPDATE ON conversations
  FOR EACH ROW EXECUTE FUNCTION kai_set_updated_at();
CREATE TRIGGER memories_updated_at
  BEFORE UPDATE ON memories
  FOR EACH ROW EXECUTE FUNCTION kai_set_updated_at();
CREATE TRIGGER agents_updated_at
  BEFORE UPDATE ON agents
  FOR EACH ROW EXECUTE FUNCTION kai_set_updated_at();
CREATE TRIGGER tools_updated_at
  BEFORE UPDATE ON tools
  FOR EACH ROW EXECUTE FUNCTION kai_set_updated_at();

ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE organizations FORCE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;
ALTER TABLE memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE memberships FORCE ROW LEVEL SECURITY;
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects FORCE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations FORCE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages FORCE ROW LEVEL SECURITY;
ALTER TABLE files ENABLE ROW LEVEL SECURITY;
ALTER TABLE files FORCE ROW LEVEL SECURITY;
ALTER TABLE memories ENABLE ROW LEVEL SECURITY;
ALTER TABLE memories FORCE ROW LEVEL SECURITY;
ALTER TABLE agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE agents FORCE ROW LEVEL SECURITY;
ALTER TABLE tools ENABLE ROW LEVEL SECURITY;
ALTER TABLE tools FORCE ROW LEVEL SECURITY;
ALTER TABLE usage_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_events FORCE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs FORCE ROW LEVEL SECURITY;

CREATE POLICY users_self ON users
  USING (id = kai_current_user())
  WITH CHECK (id = kai_current_user());

CREATE POLICY memberships_self ON memberships
  USING (user_id = kai_current_user())
  WITH CHECK (user_id = kai_current_user());

CREATE POLICY organizations_member ON organizations
  USING (
    id IN (
      SELECT organization_id FROM memberships WHERE user_id = kai_current_user()
    )
  );

CREATE POLICY projects_tenant ON projects
  USING (organization_id = kai_current_org())
  WITH CHECK (organization_id = kai_current_org());
CREATE POLICY conversations_tenant ON conversations
  USING (organization_id = kai_current_org())
  WITH CHECK (organization_id = kai_current_org());
CREATE POLICY messages_tenant ON messages
  USING (organization_id = kai_current_org())
  WITH CHECK (organization_id = kai_current_org());
CREATE POLICY files_tenant ON files
  USING (organization_id = kai_current_org())
  WITH CHECK (organization_id = kai_current_org());
CREATE POLICY memories_tenant ON memories
  USING (organization_id = kai_current_org())
  WITH CHECK (organization_id = kai_current_org());
CREATE POLICY agents_tenant ON agents
  USING (organization_id = kai_current_org())
  WITH CHECK (organization_id = kai_current_org());
CREATE POLICY tools_tenant ON tools
  USING (organization_id = kai_current_org())
  WITH CHECK (organization_id = kai_current_org());
CREATE POLICY usage_events_tenant ON usage_events
  USING (organization_id = kai_current_org())
  WITH CHECK (organization_id = kai_current_org());
CREATE POLICY audit_logs_tenant ON audit_logs
  USING (organization_id = kai_current_org())
  WITH CHECK (organization_id = kai_current_org());

GRANT USAGE ON SCHEMA public TO kai_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON
  organizations, users, memberships, projects, conversations, messages,
  files, memories, agents, tools, usage_events
TO kai_app;
GRANT SELECT, INSERT ON audit_logs TO kai_app;
GRANT USAGE ON TYPE membership_role, message_role, memory_scope TO kai_app;
