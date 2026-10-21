ALTER TABLE unit_mappings ADD COLUMN method text NOT NULL DEFAULT 'manual' CHECK(method IN ('manual','automatic'));
ALTER TABLE unit_mappings ADD COLUMN match_basis text;
CREATE TABLE mapping_auto_exclusions (
 disc_id text PRIMARY KEY,
 actor text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
