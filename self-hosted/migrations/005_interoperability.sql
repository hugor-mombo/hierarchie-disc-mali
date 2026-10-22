CREATE TABLE interop_manifests (
 version text PRIMARY KEY,
 document jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE interop_events (
 id bigserial PRIMARY KEY,
 event_id text UNIQUE NOT NULL,
 payload_hash text NOT NULL,
 received_at timestamptz NOT NULL DEFAULT now(),
 run_id text NOT NULL,
 mapping_version text NOT NULL REFERENCES interop_manifests(version),
 payload jsonb NOT NULL
);
CREATE INDEX interop_events_run ON interop_events(run_id,id DESC);
