-- Définition en lecture seule relevée le 23 octobre 2026. Référence d’audit, ne pas exécuter comme migration.
 WITH base AS (
         SELECT m.supervisor_id AS supervisor_area_uuid,
            hc.name AS supervisor_area,
            hc.uuid AS health_area_uuid,
            hc.name AS health_area,
            hc.primary_contact AS supervisor_contact_id,
            cp.name AS supervisor_name,
            hc.district_hospital AS district_uuid,
            COALESCE(cp.district, dh.name, 'Inconnue'::text) AS district,
            COALESCE(cp.region, 'Inconnue'::text) AS region,
            m.reporting_month,
            COALESCE(m.count_all_sites, 0::bigint) AS count_all_sites,
            COALESCE(m.count_active_sites, 0::bigint) AS count_active_sites
           FROM dashboard_metrics_muting m
             LEFT JOIN contactview_health_center hc ON m.supervisor_id = hc.uuid
             LEFT JOIN contactview_person cp ON hc.primary_contact = cp.uuid
             LEFT JOIN contactview_hospital dh ON hc.district_hospital = dh.uuid
          WHERE hc.primary_contact IS NOT NULL
        ), historical_rdt AS (
         SELECT sites.area AS supervisor_area_uuid,
            date_trunc('month'::text, visits.reported) AS reporting_month,
            count(*) FILTER (WHERE visits.s_patient_assessed = 'yes'::text AND visits.s_tdr_done = 'yes'::text) AS number_rdt_done,
            count(*) FILTER (WHERE visits.s_patient_assessed = 'yes'::text AND visits.s_tdr_done = 'yes'::text AND visits.s_tdr_peremption_date = 'yes'::text AND visits.s_blood_quantity = 'one_pipette'::text AND (visits.s_solvent_drops = ANY (ARRAY['yes'::text, '4'::text])) AND visits.s_tdr_required_time_to_read = 'yes'::text) AS number_rdt_correctly_done
           FROM contactview_clinic sites
             JOIN formview_visit_chw_site visits ON visits.area_id = sites.uuid
          WHERE visits.reported >= (( SELECT min(dashboard_metrics_muting.reporting_month) AS min
                   FROM dashboard_metrics_muting)) AND visits.reported < (( SELECT max(dashboard_metrics_muting.reporting_month) + '1 mon'::interval
                   FROM dashboard_metrics_muting))
          GROUP BY sites.area, (date_trunc('month'::text, visits.reported))
        ), monthly AS (
         SELECT NULL::text AS central_uuid,
            NULL::text AS central,
            NULL::text AS region_uuid,
            b.region,
            b.district_uuid,
            b.district,
            b.health_area_uuid,
            b.health_area,
            b.supervisor_area_uuid,
            b.supervisor_area,
            b.supervisor_contact_id,
            b.supervisor_name,
            b.reporting_month::date AS period_month,
            b.reporting_month::date AS reported_month,
            to_char(b.reporting_month, 'YYYY-MM'::text) AS period,
            to_char(b.reporting_month, 'YYYYMM'::text) AS period_yyyymm,
            date_part('year'::text, b.reporting_month)::integer AS year,
            date_part('quarter'::text, b.reporting_month)::integer AS quarter,
            date_part('month'::text, b.reporting_month)::integer AS month_number,
            date_part('year'::text, b.reporting_month)::integer AS reported_year,
            concat(
                CASE
                    WHEN date_part('month'::text, b.reporting_month) >= 1::double precision AND date_part('month'::text, b.reporting_month) <= 3::double precision THEN '1er trimestre'::text
                    WHEN date_part('month'::text, b.reporting_month) >= 4::double precision AND date_part('month'::text, b.reporting_month) <= 6::double precision THEN '2eme trimestre'::text
                    WHEN date_part('month'::text, b.reporting_month) >= 7::double precision AND date_part('month'::text, b.reporting_month) <= 9::double precision THEN '3eme trimestre'::text
                    WHEN date_part('month'::text, b.reporting_month) >= 10::double precision AND date_part('month'::text, b.reporting_month) <= 12::double precision THEN '4eme trimestre'::text
                    ELSE NULL::text
                END, ' ', date_part('year'::text, b.reporting_month)::integer) AS reported_quarter,
            concat(
                CASE
                    WHEN date_part('month'::text, b.reporting_month) >= 1::double precision AND date_part('month'::text, b.reporting_month) <= 6::double precision THEN '1er Semestre'::text
                    WHEN date_part('month'::text, b.reporting_month) >= 7::double precision AND date_part('month'::text, b.reporting_month) <= 12::double precision THEN '2eme Semestre'::text
                    ELSE NULL::text
                END, ' ', date_part('year'::text, b.reporting_month)::integer) AS reported_semester,
            concat(
                CASE date_part('month'::text, b.reporting_month)::integer
                    WHEN 1 THEN 'Janvier'::text
                    WHEN 2 THEN 'Fevrier'::text
                    WHEN 3 THEN 'Mars'::text
                    WHEN 4 THEN 'Avril'::text
                    WHEN 5 THEN 'Mai'::text
                    WHEN 6 THEN 'Juin'::text
                    WHEN 7 THEN 'Juillet'::text
                    WHEN 8 THEN 'Aout'::text
                    WHEN 9 THEN 'Septembre'::text
                    WHEN 10 THEN 'Octobre'::text
                    WHEN 11 THEN 'Novembre'::text
                    WHEN 12 THEN 'Decembre'::text
                    ELSE NULL::text
                END, ' ', date_part('year'::text, b.reporting_month)::integer) AS reported_month_fr,
            b.count_all_sites AS total_chw_sites_all,
            b.count_active_sites AS total_chw_sites,
            COALESCE(rma.home_visits, 0::numeric) AS total_curative_home_visits,
            COALESCE(rma.rmas_count, 0::numeric) AS sites_with_rma,
            COALESCE(rdt.number_rdt_done, 0::bigint) AS number_rdt_done,
            COALESCE(rdt.number_rdt_correctly_done, 0::bigint) AS number_rdt_correctly_done
           FROM base b
             LEFT JOIN dashboard_metrics_rma rma ON b.supervisor_area_uuid = rma.supervisor_id AND b.reporting_month = rma.reporting_month
             LEFT JOIN historical_rdt rdt ON b.supervisor_area_uuid = rdt.supervisor_area_uuid AND b.reporting_month = rdt.reporting_month
        )
 SELECT central_uuid,
    central,
    region_uuid,
    region,
    district_uuid,
    district,
    health_area_uuid,
    health_area,
    supervisor_area_uuid,
    supervisor_area,
    supervisor_contact_id,
    supervisor_name,
    period_month,
    reported_month,
    period,
    period_yyyymm,
    year,
    quarter,
    month_number,
    reported_year,
    reported_quarter,
    reported_semester,
    reported_month_fr,
    total_chw_sites_all,
    total_chw_sites,
    total_curative_home_visits,
    sites_with_rma,
    number_rdt_done,
    number_rdt_correctly_done,
    round(total_curative_home_visits / NULLIF(total_chw_sites, 0)::numeric, 4) AS avg_curative_home_visits_per_chw,
    round(total_curative_home_visits / NULLIF(sites_with_rma, 0::numeric), 4) AS avg_curative_home_visits_per_site_with_rma,
    round(number_rdt_correctly_done::numeric / NULLIF(number_rdt_done, 0)::numeric, 4) AS rdt_correctly_done_rate
   FROM monthly;