-- Définition en lecture seule relevée le 23 octobre 2026. Référence d’audit, ne pas exécuter comme migration.
 WITH bounds AS (
         SELECT '2019-01-01 00:00:00'::timestamp without time zone AS start_month,
            '2026-01-01 00:00:00'::timestamp without time zone AS end_exclusive
        ), months AS (
         SELECT generate_series(bounds.start_month, bounds.end_exclusive - '1 mon'::interval, '1 mon'::interval) AS reporting_month
           FROM bounds
        ), sites AS (
         SELECT c.uuid AS clinic_uuid,
            c.reported AS site_created_at,
            c.area AS supervisor_area_uuid,
            hc.name AS supervisor_area,
            hc.uuid AS health_area_uuid,
            hc.name AS health_area,
            hc.primary_contact AS supervisor_contact_id,
            cp.name AS supervisor_name,
            hc.district_hospital AS district_uuid,
            COALESCE(cp.district, dh.name, 'Inconnue'::text) AS district,
            COALESCE(cp.region, 'Inconnue'::text) AS region
           FROM contactview_clinic c
             JOIN contactview_health_center hc ON hc.uuid = c.area
             JOIN contactview_person cp ON cp.uuid = hc.primary_contact
             LEFT JOIN contactview_hospital dh ON dh.uuid = hc.district_hospital
          WHERE cp.name !~~* '%TEST%'::text
        ), mute_operations AS (
         SELECT formview_mute_chw_area.uuid,
            formview_mute_chw_area.place_id,
            formview_mute_chw_area.reported,
            formview_mute_chw_area.form
           FROM formview_mute_chw_area
        UNION ALL
         SELECT formview_unmute_chw_area.uuid,
            formview_unmute_chw_area.place_id,
            formview_unmute_chw_area.reported,
            formview_unmute_chw_area.form
           FROM formview_unmute_chw_area
        ), mute_history_raw AS (
         SELECT mute_operations.uuid,
            mute_operations.place_id,
            mute_operations.reported,
            mute_operations.form,
            lag(mute_operations.form) OVER (PARTITION BY mute_operations.place_id ORDER BY mute_operations.reported, mute_operations.uuid) AS previous_form,
            lag(mute_operations.reported) OVER (PARTITION BY mute_operations.place_id ORDER BY mute_operations.reported, mute_operations.uuid) AS previous_reported
           FROM mute_operations
        ), valid_mute_history AS (
         SELECT h.uuid,
            h.place_id,
            h.reported AS interval_end,
            GREATEST(COALESCE(h.previous_reported, s.site_created_at), s.site_created_at) AS interval_start,
                CASE
                    WHEN h.form = 'mute_chw_area'::text THEN 'enabled'::text
                    ELSE 'disabled'::text
                END AS state,
            row_number() OVER (PARTITION BY h.place_id ORDER BY h.reported DESC, h.uuid DESC) AS last_operation_rank
           FROM mute_history_raw h
             JOIN sites s ON s.clinic_uuid = h.place_id
          WHERE s.site_created_at IS NOT NULL AND h.reported IS NOT NULL AND NOT (h.previous_form IS NULL AND h.form = 'unmute_chw_area'::text) AND h.previous_form IS DISTINCT FROM h.form
        ), state_intervals AS (
         SELECT valid_mute_history.place_id,
            valid_mute_history.interval_start,
            valid_mute_history.interval_end,
            valid_mute_history.state
           FROM valid_mute_history
        UNION ALL
         SELECT h.place_id,
            GREATEST(h.interval_end, s.site_created_at) AS "greatest",
            b.end_exclusive,
                CASE
                    WHEN h.state = 'enabled'::text THEN 'disabled'::text
                    ELSE 'enabled'::text
                END AS "case"
           FROM valid_mute_history h
             JOIN sites s ON s.clinic_uuid = h.place_id
             CROSS JOIN bounds b
          WHERE h.last_operation_rank = 1
        UNION ALL
         SELECT s.clinic_uuid,
            s.site_created_at,
            b.end_exclusive,
            'enabled'::text AS text
           FROM sites s
             CROSS JOIN bounds b
          WHERE s.site_created_at IS NOT NULL AND NOT (EXISTS ( SELECT 1
                   FROM valid_mute_history h
                  WHERE h.place_id = s.clinic_uuid))
        ), state_intersections AS (
         SELECT i.place_id,
            m.reporting_month,
            i.state,
            i.interval_start,
            i.interval_end,
            LEAST(i.interval_end, m.reporting_month + '1 mon'::interval) - GREATEST(i.interval_start, m.reporting_month) AS intersected_duration
           FROM state_intervals i
             JOIN months m ON i.interval_start < (m.reporting_month + '1 mon'::interval) AND i.interval_end > m.reporting_month AND i.interval_end > i.interval_start
        ), ranked_monthly_states AS (
         SELECT state_intersections.place_id,
            state_intersections.reporting_month,
            state_intersections.state,
            state_intersections.interval_start,
            state_intersections.interval_end,
            state_intersections.intersected_duration,
            row_number() OVER (PARTITION BY state_intersections.place_id, state_intersections.reporting_month ORDER BY state_intersections.intersected_duration DESC, state_intersections.state, state_intersections.interval_start DESC, state_intersections.interval_end DESC) AS state_rank
           FROM state_intersections
        ), monthly_events AS (
         SELECT v.area_id AS clinic_uuid,
            date_trunc('month'::text, v.reported) AS reporting_month,
            count(v.uuid) AS supervisions_without_chw,
            0::bigint AS supervisions_with_chw,
            0::bigint AS individual_meetings
           FROM formview_visit_community_without_chw v
             CROSS JOIN bounds b
          WHERE v.reported >= b.start_month AND v.reported < b.end_exclusive
          GROUP BY v.area_id, (date_trunc('month'::text, v.reported))
        UNION ALL
         SELECT v.area_id,
            date_trunc('month'::text, v.reported) AS date_trunc,
            0::bigint AS int8,
            count(v.uuid) AS count,
            0::bigint AS int8
           FROM formview_visit_chw_site v
             CROSS JOIN bounds b
          WHERE v.reported >= b.start_month AND v.reported < b.end_exclusive
          GROUP BY v.area_id, (date_trunc('month'::text, v.reported))
        UNION ALL
         SELECT v.area_id,
            date_trunc('month'::text, v.reported) AS date_trunc,
            0::bigint AS int8,
            0::bigint AS int8,
            count(v.uuid) AS count
           FROM formview_individual_feedback v
             CROSS JOIN bounds b
          WHERE v.reported >= b.start_month AND v.reported < b.end_exclusive
          GROUP BY v.area_id, (date_trunc('month'::text, v.reported))
        ), monthly_steps AS (
         SELECT monthly_events.clinic_uuid,
            monthly_events.reporting_month,
            sum(monthly_events.supervisions_without_chw) AS supervisions_without_chw,
            sum(monthly_events.supervisions_with_chw) AS supervisions_with_chw,
            sum(monthly_events.individual_meetings) AS individual_meetings
           FROM monthly_events
          GROUP BY monthly_events.clinic_uuid, monthly_events.reporting_month
        ), site_months AS (
         SELECT s.clinic_uuid,
            s.site_created_at,
            s.supervisor_area_uuid,
            s.supervisor_area,
            s.health_area_uuid,
            s.health_area,
            s.supervisor_contact_id,
            s.supervisor_name,
            s.district_uuid,
            s.district,
            s.region,
            m.reporting_month,
            state.state,
            COALESCE(v.supervisions_without_chw, 0::numeric) AS supervisions_without_chw,
            COALESCE(v.supervisions_with_chw, 0::numeric) AS supervisions_with_chw,
            COALESCE(v.individual_meetings, 0::numeric) AS individual_meetings,
            COALESCE(v.supervisions_without_chw >= 5::numeric AND v.supervisions_with_chw >= 1::numeric AND v.individual_meetings >= 1::numeric, false) AS all_steps_completed
           FROM sites s
             CROSS JOIN months m
             LEFT JOIN ranked_monthly_states state ON state.place_id = s.clinic_uuid AND state.reporting_month = m.reporting_month AND state.state_rank = 1
             LEFT JOIN monthly_steps v ON v.clinic_uuid = s.clinic_uuid AND v.reporting_month = m.reporting_month
        ), monthly AS (
         SELECT site_months.region,
            site_months.district_uuid,
            site_months.district,
            site_months.health_area_uuid,
            site_months.health_area,
            site_months.supervisor_area_uuid,
            site_months.supervisor_area,
            site_months.supervisor_contact_id,
            site_months.supervisor_name,
            site_months.reporting_month,
            count(*) FILTER (WHERE site_months.state IS NOT NULL) AS total_chw_sites_all,
            count(*) FILTER (WHERE site_months.state = 'enabled'::text) AS denominator,
            count(*) FILTER (WHERE site_months.state = 'enabled'::text AND site_months.all_steps_completed) AS numerator,
            count(*) FILTER (WHERE site_months.state = 'enabled'::text AND site_months.supervisions_with_chw >= 1::numeric) AS active_sites_with_chw_visit,
            count(*) FILTER (WHERE site_months.state = 'disabled'::text AND site_months.all_steps_completed) AS inactive_sites_with_all_steps,
            count(*) FILTER (WHERE site_months.site_created_at IS NULL) AS sites_without_creation_date,
            COALESCE(sum(site_months.supervisions_without_chw) FILTER (WHERE site_months.state = 'enabled'::text), 0::numeric) AS supervisions_without_chw,
            COALESCE(sum(site_months.supervisions_with_chw) FILTER (WHERE site_months.state = 'enabled'::text), 0::numeric) AS supervisions_with_chw,
            COALESCE(sum(site_months.individual_meetings) FILTER (WHERE site_months.state = 'enabled'::text), 0::numeric) AS individual_meetings
           FROM site_months
          GROUP BY site_months.region, site_months.district_uuid, site_months.district, site_months.health_area_uuid, site_months.health_area, site_months.supervisor_area_uuid, site_months.supervisor_area, site_months.supervisor_contact_id, site_months.supervisor_name, site_months.reporting_month
        )
 SELECT NULL::text AS central_uuid,
    NULL::text AS central,
    NULL::text AS region_uuid,
    region,
    district_uuid,
    district,
    health_area_uuid,
    health_area,
    supervisor_area_uuid,
    supervisor_area,
    supervisor_contact_id,
    supervisor_name,
    reporting_month::date AS period_month,
    reporting_month::date AS reported_month,
    to_char(reporting_month, 'YYYY-MM'::text) AS period,
    to_char(reporting_month, 'YYYYMM'::text) AS period_yyyymm,
    EXTRACT(year FROM reporting_month)::integer AS year,
    EXTRACT(quarter FROM reporting_month)::integer AS quarter,
    EXTRACT(month FROM reporting_month)::integer AS month_number,
    EXTRACT(year FROM reporting_month)::integer AS reported_year,
    concat(
        CASE EXTRACT(quarter FROM reporting_month)::integer
            WHEN 1 THEN '1er trimestre'::text
            WHEN 2 THEN '2eme trimestre'::text
            WHEN 3 THEN '3eme trimestre'::text
            WHEN 4 THEN '4eme trimestre'::text
            ELSE NULL::text
        END, ' ', EXTRACT(year FROM reporting_month)::integer) AS reported_quarter,
    concat(
        CASE
            WHEN EXTRACT(month FROM reporting_month) <= 6::numeric THEN '1er Semestre'::text
            ELSE '2eme Semestre'::text
        END, ' ', EXTRACT(year FROM reporting_month)::integer) AS reported_semester,
    concat((ARRAY['Janvier'::text, 'Fevrier'::text, 'Mars'::text, 'Avril'::text, 'Mai'::text, 'Juin'::text, 'Juillet'::text, 'Aout'::text, 'Septembre'::text, 'Octobre'::text, 'Novembre'::text, 'Decembre'::text])[EXTRACT(month FROM reporting_month)::integer], ' ', EXTRACT(year FROM reporting_month)::integer) AS reported_month_fr,
    'monthly_supervision_all_steps_rate'::text AS indicator_code,
    'Proportion des ASC ayant recu une supervision mensuelle avec toutes les etapes'::text AS indicator_label,
    'Supervision'::text AS indicator_group,
    'rate'::text AS metric_type,
    numerator,
    denominator,
    round(numerator::numeric / NULLIF(denominator, 0)::numeric, 4) AS indicator_value,
    round(100::numeric * numerator::numeric / NULLIF(denominator, 0)::numeric, 2) AS percentage,
    numerator AS chw_sites_supervised_all_steps,
    denominator AS total_chw_sites,
    total_chw_sites_all,
    active_sites_with_chw_visit,
    inactive_sites_with_all_steps,
    sites_without_creation_date,
    supervisions_without_chw,
    supervisions_with_chw,
    individual_meetings
   FROM monthly;