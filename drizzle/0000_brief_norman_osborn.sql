CREATE TABLE `audit_events` (
	`id` text PRIMARY KEY NOT NULL,
	`created_at` text NOT NULL,
	`actor` text NOT NULL,
	`action` text NOT NULL,
	`detail` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `unit_mappings` (
	`disc_id` text PRIMARY KEY NOT NULL,
	`dhis_id` text NOT NULL,
	`created_at` text NOT NULL,
	`actor` text NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `unit_mappings_dhis_id_unique` ON `unit_mappings` (`dhis_id`);--> statement-breakpoint
CREATE TABLE `app_records` (
	`key` text PRIMARY KEY NOT NULL,
	`value` text NOT NULL
);
