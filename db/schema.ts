import { sqliteTable, text } from 'drizzle-orm/sqlite-core';
export const records = sqliteTable('app_records', {
  key: text('key').primaryKey(), value: text('value').notNull(),
});
export const mappings = sqliteTable('unit_mappings', {
  discId: text('disc_id').primaryKey(), dhisId: text('dhis_id').notNull().unique(),
  createdAt: text('created_at').notNull(), actor: text('actor').notNull(),
});
export const audit = sqliteTable('audit_events', {
  id: text('id').primaryKey(), createdAt: text('created_at').notNull(),
  actor: text('actor').notNull(), action: text('action').notNull(), detail: text('detail').notNull(),
});
