-- Données entièrement synthétiques : tests de frontières et d'exclusions.
\set ON_ERROR_STOP on
CREATE TABLE mv_superset_sd_portfolio (
 chw_site_uuid text,chw_site text,region_uuid text,region text,district_uuid text,district text,
 health_area_uuid text,health_area text,supervisor_area_uuid text,supervisor_area text,snapshot_date date);
CREATE TABLE contactview_metadata (uuid text PRIMARY KEY,parent_uuid text,contact_type text,reported timestamptz);
CREATE INDEX ON contactview_metadata(parent_uuid);
CREATE TABLE couchdb(doc jsonb);
CREATE UNIQUE INDEX ON couchdb((doc->>'_id'));
CREATE TABLE mv_chw_site_hierarchy_reporting(chw_site_uuid text PRIMARY KEY,chw_site text,
 region_uuid text,region text,district_uuid text,district text,health_area_uuid text,health_area text,reported_date date);
CREATE TABLE mv_asc_v2_report_monthly(reported_month date,site_key text,quality text,report_count bigint,last_reported timestamptz,refreshed_at timestamptz);
CREATE TABLE mv_superset_sd_chw_monthly_status(chw_site_uuid text,reported_month date,
 supervisor_uuid text,supervisor_name text,assignment_status text,
 visit_chw_site_reports bigint,visit_community_without_chw_reports bigint,individual_feedback_reports bigint,
 has_visit_chw_site integer,received_sd_three_forms integer,received_sd_complete_quota integer,last_activity_at timestamptz);
INSERT INTO mv_superset_sd_portfolio
SELECT id,name,'R1','Région',district,'District homonyme',area,'CSCOM homonyme','Z'||id,'Zone',CURRENT_DATE-3
FROM (VALUES ('A','Site A','D11111111','H11111111'),('B','Site B','D11111111','H11111111'),
 ('C','Site C','D11111111','H11111111'),('D','Site D NE','D11111111','H11111111'),
 ('E','Site nouveau','D11111111','H11111111'),('F','Date inconnue','D11111111','H11111111'),
 ('G','Site G','D22222222','H22222222'),('H','Site H','D11111111','H33333333')) v(id,name,district,area);
-- Une branche incomplète reste dans le référentiel ; pas de jointure destructive.
UPDATE mv_superset_sd_portfolio SET region_uuid=NULL,region=NULL,district_uuid=NULL,district=NULL,health_area_uuid=NULL,health_area=NULL WHERE chw_site_uuid='H';
INSERT INTO contactview_metadata
SELECT chw_site_uuid,NULL,'c60_chw_site',CASE WHEN chw_site_uuid='E' THEN date_trunc('month',CURRENT_DATE)
 WHEN chw_site_uuid='F' THEN NULL ELSE date_trunc('month',CURRENT_DATE)-interval '4 months' END
FROM mv_superset_sd_portfolio;
INSERT INTO contactview_metadata
SELECT 'contact-'||chw_site_uuid,chw_site_uuid,'c62_chw',CURRENT_TIMESTAMP FROM mv_superset_sd_portfolio WHERE chw_site_uuid NOT IN('B','F');
INSERT INTO couchdb SELECT jsonb_build_object('_id',uuid,'username',CASE WHEN parent_uuid='C' THEN 'formation-1' ELSE 'asc-test' END)
FROM contactview_metadata WHERE contact_type='c62_chw';
INSERT INTO mv_chw_site_hierarchy_reporting
SELECT p.chw_site_uuid,p.chw_site,p.region_uuid,p.region,p.district_uuid,p.district,p.health_area_uuid,p.health_area,m.reported::date
FROM mv_superset_sd_portfolio p JOIN contactview_metadata m ON m.uuid=p.chw_site_uuid WHERE p.chw_site_uuid IN('A','E','G','H');
INSERT INTO mv_asc_v2_report_monthly VALUES
 (date_trunc('month',CURRENT_DATE)-interval '1 month','A','attribue',3,CURRENT_DATE-10,CURRENT_TIMESTAMP),
 (date_trunc('month',CURRENT_DATE)-interval '2 months','A','attribue',2,CURRENT_DATE-40,CURRENT_TIMESTAMP);
INSERT INTO mv_superset_sd_chw_monthly_status
SELECT chw_site_uuid,date_trunc('month',CURRENT_DATE)-m*interval '1 month',NULL,NULL,'unassigned',
 CASE WHEN chw_site_uuid IN('A','E') THEN 1 ELSE 0 END,0,0,
 CASE WHEN chw_site_uuid IN('A','E') THEN 1 ELSE 0 END,0,0,NULL
FROM mv_superset_sd_portfolio CROSS JOIN generate_series(1,2) m;
CREATE MATERIALIZED VIEW mv_disc_site_registry_v1 AS
\ir ../sql/site-registry/registry.sql
;
CREATE UNIQUE INDEX ON mv_disc_site_registry_v1(site_uuid);
CREATE VIEW v_disc_site_registry_labels_v1 AS
\ir ../sql/site-registry/geography.sql
;
CREATE VIEW common_monthly AS
\ir ../sql/site-registry/monthly.sql
;
CREATE VIEW asc_monthly AS
\ir ../sql/sites_monthly.sql
;
CREATE VIEW sd_monthly AS
\ir ../sql/supervision/disc_sites.sql
;
DO $$
DECLARE n integer;
BEGIN
 ASSERT (SELECT count(*) FROM mv_disc_site_registry_v1)=8,'Inventory must retain excluded contacts and unknown dates';
 ASSERT (SELECT contact_status FROM mv_disc_site_registry_v1 WHERE site_uuid='B')='Sans contact ASC dans le relevé courant';
 ASSERT (SELECT contact_status FROM mv_disc_site_registry_v1 WHERE site_uuid='C')='Contacts de formation uniquement';
 ASSERT (SELECT contact_status FROM mv_disc_site_registry_v1 WHERE site_uuid='D')='Nom exclu par la règle ASC (zz / NE)';
 ASSERT (SELECT training_contacts FROM mv_disc_site_registry_v1 WHERE site_uuid='A') IS NULL,'Eligible contact audit not fabricated';
 ASSERT NOT EXISTS(SELECT site_uuid,reported_month FROM common_monthly GROUP BY 1,2 HAVING count(*)<>1),'Site-month grain';
 ASSERT (SELECT count(*) FROM common_monthly WHERE reported_month=date_trunc('month',CURRENT_DATE)-interval '1 month' AND in_period=1)=7,'Creation boundary and unknown-date inclusion';
 ASSERT (SELECT count(*) FROM common_monthly WHERE reported_month=date_trunc('month',CURRENT_DATE)-interval '1 month' AND asc_in_period=1)=3,'ASC cohort boundary';
 ASSERT (SELECT in_period FROM common_monthly WHERE site_uuid='E' AND reported_month=date_trunc('month',CURRENT_DATE))=1,'Creation in month included';
 ASSERT (SELECT count(*) FROM asc_monthly WHERE reported_month=date_trunc('month',CURRENT_DATE)-interval '1 month')=3,'Native ASC count preserved';
 ASSERT (SELECT sum(report_count) FROM asc_monthly WHERE reported_month=date_trunc('month',CURRENT_DATE)-interval '1 month')=3,'ASC report volume preserved';
 ASSERT (SELECT count(*) FROM sd_monthly WHERE reported_month=date_trunc('month',CURRENT_DATE)-interval '1 month')=7,'SD and common denominators equal';
 ASSERT (SELECT sum(visited) FROM sd_monthly WHERE reported_month=date_trunc('month',CURRENT_DATE)-interval '1 month')=1,'Post-creation reports excluded from period';
 ASSERT (SELECT count(DISTINCT site_uuid) FILTER(WHERE in_period=1 AND asc_in_period=1 AND asc_report_count>0) FROM common_monthly WHERE reported_month<date_trunc('month',CURRENT_DATE))=1,'Multi-month distinct count';
 ASSERT NOT EXISTS(SELECT district FROM v_disc_site_registry_labels_v1 GROUP BY 1 HAVING count(DISTINCT district_uuid)>1),'District homonyms';
 ASSERT NOT EXISTS(SELECT cscom FROM v_disc_site_registry_labels_v1 GROUP BY 1 HAVING count(DISTINCT health_area_uuid)>1),'CSCOM homonyms';
 ASSERT (SELECT count(*) FROM common_monthly WHERE site_uuid='H')=14,'Missing branch remains visible';
 ASSERT NOT EXISTS(SELECT 1 FROM common_monthly WHERE reported_month=date_trunc('month',CURRENT_DATE) AND sd_available<>0),'No fabricated current SD availability';
END $$;
SELECT 'Référentiel commun : frontières, exclusions, grain, homonymes et conservation OK' AS result;
