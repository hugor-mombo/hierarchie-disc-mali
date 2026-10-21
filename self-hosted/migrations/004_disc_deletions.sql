CREATE TABLE deletion_requests (
 id uuid PRIMARY KEY, unit_id text NOT NULL, unit_name text NOT NULL,
 reason text NOT NULL, endpoint text NOT NULL, reference_endpoint text NOT NULL, scope jsonb NOT NULL,
 status text NOT NULL CHECK(status IN ('prepare_queued','preparing','prepared','queued','executing','succeeded','failed','uncertain','cancelled')),
 prepared_plan jsonb, result jsonb, error text,
 requested_by uuid NOT NULL REFERENCES app_users(id), executor uuid REFERENCES app_users(id),
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX one_open_deletion ON deletion_requests ((true)) WHERE status NOT IN ('succeeded','failed','cancelled');
