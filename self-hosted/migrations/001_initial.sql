CREATE TABLE IF NOT EXISTS app_users (
 id uuid PRIMARY KEY, username text NOT NULL UNIQUE, display_name text NOT NULL,
 password_hash text NOT NULL, role text NOT NULL CHECK(role IN ('viewer','editor','reviewer','admin')),
 enabled boolean NOT NULL DEFAULT true, must_change_password boolean NOT NULL DEFAULT true,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS app_sessions (
 token_hash text PRIMARY KEY, user_id uuid NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
 expires_at timestamptz NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS sessions_expiry ON app_sessions(expires_at);
CREATE TABLE IF NOT EXISTS login_attempts (key text PRIMARY KEY, attempts integer NOT NULL, reset_at timestamptz NOT NULL);
CREATE TABLE IF NOT EXISTS app_records (key text PRIMARY KEY, value jsonb NOT NULL);
CREATE TABLE IF NOT EXISTS unit_mappings (
 disc_id text PRIMARY KEY, dhis_id text UNIQUE NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),actor text NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_events (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, created_at timestamptz NOT NULL DEFAULT now(),
 actor text NOT NULL, action text NOT NULL, detail jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS move_requests (
 id uuid PRIMARY KEY, source text NOT NULL CHECK(source IN ('disc','dhis')),
 unit_id text NOT NULL, new_parent_id text NOT NULL, expected_parent_id text NOT NULL,
 unit_name text NOT NULL, parent_name text NOT NULL, before_path text NOT NULL, after_path text NOT NULL,
 endpoint text NOT NULL, reason text NOT NULL, impact_count integer NOT NULL,
 status text NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','prepare_queued','preparing','prepared','ready','execute_queued','executing','succeeded','failed','uncertain','rejected','cancelled')),
 requested_by uuid NOT NULL REFERENCES app_users(id), approved_by uuid REFERENCES app_users(id),
 plan_approved_by uuid REFERENCES app_users(id), executor uuid REFERENCES app_users(id),
 prepared_plan jsonb, error text, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS one_open_move ON move_requests(source,unit_id) WHERE status NOT IN ('succeeded','failed','rejected','cancelled');
