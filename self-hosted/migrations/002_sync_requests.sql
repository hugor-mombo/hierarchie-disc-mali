CREATE TABLE sync_requests (
 id uuid PRIMARY KEY,
 origin_source text NOT NULL CHECK(origin_source IN ('disc','dhis')),
 target_source text NOT NULL CHECK(target_source IN ('disc','dhis')),
 origin_id text NOT NULL, target_id text,
 operation text NOT NULL CHECK(operation IN ('create','rename','move')),
 plan jsonb NOT NULL, reason text NOT NULL,
 status text NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','queued','executing','succeeded','failed','uncertain','cancelled')),
 requested_by uuid NOT NULL REFERENCES app_users(id), executor uuid REFERENCES app_users(id),
 result jsonb, error text,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 CHECK(origin_source<>target_source)
);
CREATE UNIQUE INDEX one_open_sync_origin ON sync_requests(origin_source,origin_id)
 WHERE status NOT IN ('succeeded','failed','cancelled');
CREATE UNIQUE INDEX one_open_sync_target ON sync_requests(target_source,target_id)
 WHERE target_id IS NOT NULL AND status NOT IN ('succeeded','failed','cancelled');
