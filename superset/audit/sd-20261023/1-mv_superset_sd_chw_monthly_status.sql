-- Définition en lecture seule relevée le 23 octobre 2026. Référence d’audit, ne pas exécuter comme migration.
 WITH params AS (
         SELECT '2026-01-01'::date AS start_month,
            date_trunc('month'::text, CURRENT_DATE - '1 mon'::interval)::date AS end_month
        ), places AS (
         SELECT mv_superset_sd_portfolio.central_uuid,
            mv_superset_sd_portfolio.central,
            mv_superset_sd_portfolio.region_uuid,
            mv_superset_sd_portfolio.region,
            mv_superset_sd_portfolio.district_uuid,
            mv_superset_sd_portfolio.district,
            mv_superset_sd_portfolio.health_area_uuid,
            mv_superset_sd_portfolio.health_area,
            mv_superset_sd_portfolio.supervisor_area_uuid,
            mv_superset_sd_portfolio.supervisor_area,
            mv_superset_sd_portfolio.chw_site_uuid,
            mv_superset_sd_portfolio.chw_site,
            mv_superset_sd_portfolio.supervisor_key,
            mv_superset_sd_portfolio.supervisor_uuid,
            mv_superset_sd_portfolio.supervisor_username,
            mv_superset_sd_portfolio.supervisor_name,
            mv_superset_sd_portfolio.supervisor_first_name,
            mv_superset_sd_portfolio.supervisor_last_name,
            mv_superset_sd_portfolio.supervisor_phone,
            mv_superset_sd_portfolio.supervisor_email,
            mv_superset_sd_portfolio.supervisor_sex,
            mv_superset_sd_portfolio.assignment_status,
            mv_superset_sd_portfolio.assignment_source,
            mv_superset_sd_portfolio.assignment_candidates,
            mv_superset_sd_portfolio.first_geolocation_date,
            mv_superset_sd_portfolio.last_geolocation_date,
            mv_superset_sd_portfolio.geolocation_report_count,
            mv_superset_sd_portfolio.is_geolocated,
            mv_superset_sd_portfolio.snapshot_date
           FROM mv_superset_sd_portfolio
        ), months AS (
         SELECT generate_series((( SELECT params.start_month
                   FROM params))::timestamp with time zone, (( SELECT params.end_month
                   FROM params))::timestamp with time zone, '1 mon'::interval)::date AS period_month
        ), site_months AS (
         SELECT p.central_uuid,
            p.central,
            p.region_uuid,
            p.region,
            p.district_uuid,
            p.district,
            p.health_area_uuid,
            p.health_area,
            p.supervisor_area_uuid,
            p.supervisor_area,
            p.chw_site_uuid,
            p.chw_site,
            p.supervisor_key,
            p.supervisor_uuid,
            p.supervisor_username,
            p.supervisor_name,
            p.supervisor_first_name,
            p.supervisor_last_name,
            p.supervisor_phone,
            p.supervisor_email,
            p.supervisor_sex,
            p.assignment_status,
            p.assignment_source,
            m.period_month,
            m.period_month AS reported_month,
            to_char(m.period_month::timestamp with time zone, 'YYYY-MM'::text) AS period,
            to_char(m.period_month::timestamp with time zone, 'YYYYMM'::text) AS period_yyyymm,
            date_part('year'::text, m.period_month)::integer AS year,
            date_part('quarter'::text, m.period_month)::integer AS quarter,
            date_part('month'::text, m.period_month)::integer AS month_number,
            date_part('year'::text, m.period_month)::integer AS reported_year,
            get_quarterly_period(m.period_month) AS reported_quarter,
            get_semester_period(m.period_month) AS reported_semester,
            get_month_year_fr(m.period_month) AS reported_month_fr
           FROM places p
             CROSS JOIN months m
        ), activity AS (
         SELECT mv_superset_sd_activity_events.chw_site_uuid,
            mv_superset_sd_activity_events.reported_month AS period_month,
            count(*) FILTER (WHERE mv_superset_sd_activity_events.form_name = 'supervision_calendar'::text) AS scheduled_visit_reports,
            count(*) FILTER (WHERE mv_superset_sd_activity_events.form_name = 'supervision_visit_realization'::text) AS visit_realization_reports,
            count(*) FILTER (WHERE mv_superset_sd_activity_events.form_name = 'supervision_visit_realization'::text AND mv_superset_sd_activity_events.is_visit_done = 1) AS planned_visit_done_reports,
            count(*) FILTER (WHERE mv_superset_sd_activity_events.form_name = 'supervision_visit_realization'::text AND mv_superset_sd_activity_events.is_steps_done = 1) AS planned_visit_all_steps_done_reports,
            count(*) FILTER (WHERE mv_superset_sd_activity_events.form_name = 'supervision_with_chw_confirmation'::text) AS with_chw_confirmation_reports,
            count(*) FILTER (WHERE mv_superset_sd_activity_events.form_name = 'supervision_without_chw_confirmation'::text) AS without_chw_confirmation_reports,
            count(*) FILTER (WHERE mv_superset_sd_activity_events.form_name = 'visit_chw_site'::text) AS visit_chw_site_reports,
            count(*) FILTER (WHERE mv_superset_sd_activity_events.form_name = 'visit_community_without_chw'::text) AS visit_community_without_chw_reports,
            count(*) FILTER (WHERE mv_superset_sd_activity_events.form_name = 'individual_feedback'::text) AS individual_feedback_reports,
            count(*) FILTER (WHERE mv_superset_sd_activity_events.form_name = 'individual_feedback_confirmation'::text) AS individual_feedback_confirmation_reports,
            count(*) FILTER (WHERE mv_superset_sd_activity_events.form_name = 'location_gps'::text) AS location_gps_reports,
            count(*) FILTER (WHERE mv_superset_sd_activity_events.is_not_done_supervisor_unavailable = 1) AS not_done_supervisor_unavailable_reports,
            count(*) FILTER (WHERE mv_superset_sd_activity_events.is_rescheduled_report = 1) AS rescheduled_reports,
            count(*) FILTER (WHERE mv_superset_sd_activity_events.is_patient_assessed = 1) AS patient_assessed_reports,
            count(*) FILTER (WHERE mv_superset_sd_activity_events.is_rdt_done = 1) AS rdt_done_reports,
            count(*) FILTER (WHERE mv_superset_sd_activity_events.is_rdt_correctly_done = 1) AS rdt_correctly_done_reports,
            count(*) FILTER (WHERE mv_superset_sd_activity_events.has_acceptable_score = 1) AS acceptable_score_reports,
            max(mv_superset_sd_activity_events.final_score) FILTER (WHERE mv_superset_sd_activity_events.form_name = 'visit_chw_site'::text) AS best_final_score,
            max(mv_superset_sd_activity_events.reported_at) AS last_activity_at
           FROM mv_superset_sd_activity_events
          WHERE mv_superset_sd_activity_events.chw_site_uuid IS NOT NULL
          GROUP BY mv_superset_sd_activity_events.chw_site_uuid, mv_superset_sd_activity_events.reported_month
        ), gps_ever AS (
         SELECT mv_superset_sd_site_geolocation.chw_site_uuid,
            mv_superset_sd_site_geolocation.first_geolocation_date,
            mv_superset_sd_site_geolocation.last_geolocation_date
           FROM mv_superset_sd_site_geolocation
        ), base AS (
         SELECT sm.central_uuid,
            sm.central,
            sm.region_uuid,
            sm.region,
            sm.district_uuid,
            sm.district,
            sm.health_area_uuid,
            sm.health_area,
            sm.supervisor_area_uuid,
            sm.supervisor_area,
            sm.chw_site_uuid,
            sm.chw_site,
            sm.supervisor_key,
            sm.supervisor_uuid,
            sm.supervisor_username,
            sm.supervisor_name,
            sm.supervisor_first_name,
            sm.supervisor_last_name,
            sm.supervisor_phone,
            sm.supervisor_email,
            sm.supervisor_sex,
            sm.assignment_status,
            sm.assignment_source,
            sm.period_month,
            sm.reported_month,
            sm.period,
            sm.period_yyyymm,
            sm.year,
            sm.quarter,
            sm.month_number,
            sm.reported_year,
            sm.reported_quarter,
            sm.reported_semester,
            sm.reported_month_fr,
            COALESCE(a.scheduled_visit_reports, 0::bigint) AS scheduled_visit_reports,
            COALESCE(a.visit_realization_reports, 0::bigint) AS visit_realization_reports,
            COALESCE(a.planned_visit_done_reports, 0::bigint) AS planned_visit_done_reports,
            COALESCE(a.planned_visit_all_steps_done_reports, 0::bigint) AS planned_visit_all_steps_done_reports,
            COALESCE(a.with_chw_confirmation_reports, 0::bigint) AS with_chw_confirmation_reports,
            COALESCE(a.without_chw_confirmation_reports, 0::bigint) AS without_chw_confirmation_reports,
            COALESCE(a.visit_chw_site_reports, 0::bigint) AS visit_chw_site_reports,
            COALESCE(a.visit_community_without_chw_reports, 0::bigint) AS visit_community_without_chw_reports,
            COALESCE(a.individual_feedback_reports, 0::bigint) AS individual_feedback_reports,
            COALESCE(a.individual_feedback_confirmation_reports, 0::bigint) AS individual_feedback_confirmation_reports,
            COALESCE(a.location_gps_reports, 0::bigint) AS location_gps_reports,
            COALESCE(a.not_done_supervisor_unavailable_reports, 0::bigint) AS not_done_supervisor_unavailable_reports,
            COALESCE(a.rescheduled_reports, 0::bigint) AS rescheduled_reports,
            COALESCE(a.patient_assessed_reports, 0::bigint) AS patient_assessed_reports,
            COALESCE(a.rdt_done_reports, 0::bigint) AS rdt_done_reports,
            COALESCE(a.rdt_correctly_done_reports, 0::bigint) AS rdt_correctly_done_reports,
            COALESCE(a.acceptable_score_reports, 0::bigint) AS acceptable_score_reports,
            a.best_final_score,
            a.last_activity_at,
            ge.first_geolocation_date,
            ge.last_geolocation_date
           FROM site_months sm
             LEFT JOIN activity a ON sm.chw_site_uuid = a.chw_site_uuid AND sm.period_month = a.period_month
             LEFT JOIN gps_ever ge ON sm.chw_site_uuid = ge.chw_site_uuid
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
    chw_site_uuid,
    chw_site,
    supervisor_key,
    supervisor_uuid,
    supervisor_username,
    supervisor_name,
    supervisor_first_name,
    supervisor_last_name,
    supervisor_phone,
    supervisor_email,
    supervisor_sex,
    assignment_status,
    assignment_source,
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
    scheduled_visit_reports,
    visit_realization_reports,
    planned_visit_done_reports,
    planned_visit_all_steps_done_reports,
    with_chw_confirmation_reports,
    without_chw_confirmation_reports,
    visit_chw_site_reports,
    visit_community_without_chw_reports,
    individual_feedback_reports,
    individual_feedback_confirmation_reports,
    location_gps_reports,
    not_done_supervisor_unavailable_reports,
    rescheduled_reports,
    patient_assessed_reports,
    rdt_done_reports,
    rdt_correctly_done_reports,
    acceptable_score_reports,
    best_final_score,
    last_activity_at,
    first_geolocation_date,
    last_geolocation_date,
    1 AS required_visit_chw_site_for_feedback,
    5 AS required_visit_community_without_chw_for_feedback,
    LEAST(floor(visit_chw_site_reports::numeric / 1::numeric), floor(visit_community_without_chw_reports::numeric / 5::numeric))::integer AS feedback_quota_available,
    GREATEST(LEAST(floor(visit_chw_site_reports::numeric / 1::numeric), floor(visit_community_without_chw_reports::numeric / 5::numeric))::integer - individual_feedback_reports, 0::bigint) AS feedback_gap_for_next_individual_feedback,
        CASE
            WHEN scheduled_visit_reports > 0 THEN 1
            ELSE 0
        END AS has_scheduled_visit,
        CASE
            WHEN planned_visit_done_reports > 0 THEN 1
            ELSE 0
        END AS has_planned_visit_done,
        CASE
            WHEN planned_visit_all_steps_done_reports > 0 THEN 1
            ELSE 0
        END AS has_planned_visit_all_steps_done,
        CASE
            WHEN visit_chw_site_reports > 0 THEN 1
            ELSE 0
        END AS has_visit_chw_site,
        CASE
            WHEN visit_community_without_chw_reports > 0 THEN 1
            ELSE 0
        END AS has_visit_community_without_chw,
        CASE
            WHEN visit_community_without_chw_reports >= 5 THEN 1
            ELSE 0
        END AS has_minimum_5_community_visits_without_chw,
        CASE
            WHEN individual_feedback_reports > 0 THEN 1
            ELSE 0
        END AS has_individual_feedback,
        CASE
            WHEN individual_feedback_confirmation_reports > 0 THEN 1
            ELSE 0
        END AS has_individual_feedback_confirmation,
        CASE
            WHEN first_geolocation_date < (period_month + '1 mon'::interval) THEN 1
            ELSE 0
        END AS has_location_gps_ever,
        CASE
            WHEN first_geolocation_date IS NOT NULL THEN 1
            ELSE 0
        END AS has_location_gps_current,
        CASE
            WHEN date_trunc('month'::text, first_geolocation_date::timestamp with time zone)::date = period_month THEN 1
            ELSE 0
        END AS is_first_geolocation_in_month,
        CASE
            WHEN scheduled_visit_reports > 0 AND planned_visit_done_reports > 0 THEN 1
            ELSE 0
        END AS has_planned_visit_done_on_scheduled_site,
        CASE
            WHEN location_gps_reports > 0 THEN 1
            ELSE 0
        END AS has_location_gps_in_month,
        CASE
            WHEN patient_assessed_reports > 0 THEN 1
            ELSE 0
        END AS has_patient_assessed,
        CASE
            WHEN rdt_done_reports > 0 THEN 1
            ELSE 0
        END AS has_rdt_done,
        CASE
            WHEN rdt_correctly_done_reports > 0 THEN 1
            ELSE 0
        END AS has_rdt_correctly_done,
        CASE
            WHEN acceptable_score_reports > 0 THEN 1
            ELSE 0
        END AS has_acceptable_score,
        CASE
            WHEN visit_chw_site_reports >= 1 AND visit_community_without_chw_reports >= 1 AND individual_feedback_reports >= 1 THEN 1
            ELSE 0
        END AS received_sd_three_forms,
        CASE
            WHEN visit_chw_site_reports >= 1 AND visit_community_without_chw_reports >= 5 AND individual_feedback_reports >= 1 THEN 1
            ELSE 0
        END AS received_sd_complete_quota,
        CASE
            WHEN LEAST(floor(visit_chw_site_reports::numeric / 1::numeric), floor(visit_community_without_chw_reports::numeric / 5::numeric))::integer > individual_feedback_reports THEN 1
            ELSE 0
        END AS is_ready_for_individual_feedback
   FROM base;