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
          WHERE mv_superset_sd_portfolio.supervisor_area_uuid IS NOT NULL
        ), supervisor_places AS (
         SELECT DISTINCT places.central_uuid,
            places.central,
            places.region_uuid,
            places.region,
            places.district_uuid,
            places.district,
            places.health_area_uuid,
            places.health_area,
            places.supervisor_area_uuid,
            places.supervisor_area
           FROM places
          WHERE places.supervisor_area_uuid IS NOT NULL
        ), raw_events AS (
         SELECT formview_supervision_calendar.uuid,
            'supervision_calendar'::text AS form_name,
            'planned_visit'::text AS activity_code,
            'Planification supervision'::text AS activity_label,
            10 AS activity_order,
            formview_supervision_calendar.reported_by,
            formview_supervision_calendar.reported_by_parent AS supervisor_area_uuid,
            formview_supervision_calendar.source,
            formview_supervision_calendar.source_id,
            formview_supervision_calendar._id AS chw_site_uuid,
            formview_supervision_calendar.name AS chw_site,
            formview_supervision_calendar.contact__id AS chw_contact_id,
            formview_supervision_calendar.contact_name AS chw_contact_name,
            formview_supervision_calendar.place_id,
            formview_supervision_calendar.place_name,
            formview_supervision_calendar.reported AS reported_at,
            formview_supervision_calendar.supervision_date AS planned_visit_at,
            NULL::timestamp with time zone AS rescheduled_visit_at,
            NULL::text AS has_visit_been_made,
            NULL::text AS why_visit_not_done,
            NULL::text AS reason_visit_not_done,
            NULL::text AS have_schedule_another_visit,
            NULL::text AS steps_been_done,
            NULL::text AS is_rescheduled,
            NULL::text AS next_visit_date,
            NULL::text AS s_patient_assessed,
            NULL::text AS s_tdr_done,
            NULL::text AS rdt_correctly_carried_out,
            NULL::numeric AS final_score
           FROM formview_supervision_calendar
        UNION ALL
         SELECT formview_supervision_visit_realization.uuid,
            'supervision_visit_realization'::text AS form_name,
            'planned_visit_realization'::text AS activity_code,
            'Realisation visite planifiee'::text AS activity_label,
            20 AS activity_order,
            formview_supervision_visit_realization.reported_by,
            formview_supervision_visit_realization.reported_by_parent AS supervisor_area_uuid,
            formview_supervision_visit_realization.source,
            formview_supervision_visit_realization.source_id,
            formview_supervision_visit_realization._id AS chw_site_uuid,
            formview_supervision_visit_realization.name AS chw_site,
            NULL::text AS chw_contact_id,
            NULL::text AS chw_contact_name,
            formview_supervision_visit_realization.place_id,
            formview_supervision_visit_realization.place_name,
            formview_supervision_visit_realization.reported AS reported_at,
            NULL::timestamp with time zone AS planned_visit_at,
            formview_supervision_visit_realization.which_date AS rescheduled_visit_at,
            formview_supervision_visit_realization.has_visit_been_made,
            formview_supervision_visit_realization.why_visit_not_done,
            formview_supervision_visit_realization.specify_why_visit_not_done AS reason_visit_not_done,
            formview_supervision_visit_realization.have_schedule_another_visit,
            formview_supervision_visit_realization.steps_been_done,
            NULL::text AS is_rescheduled,
            NULL::text AS next_visit_date,
            NULL::text AS s_patient_assessed,
            NULL::text AS s_tdr_done,
            NULL::text AS rdt_correctly_carried_out,
            NULL::numeric AS final_score
           FROM formview_supervision_visit_realization
        UNION ALL
         SELECT formview_supervision_with_chw_confirmation.uuid,
            'supervision_with_chw_confirmation'::text AS form_name,
            'visit_with_chw_confirmation'::text AS activity_code,
            'Confirmation supervision avec ASC'::text AS activity_label,
            30 AS activity_order,
            formview_supervision_with_chw_confirmation.reported_by,
            formview_supervision_with_chw_confirmation.reported_by_parent AS supervisor_area_uuid,
            formview_supervision_with_chw_confirmation.source,
            formview_supervision_with_chw_confirmation.source_id,
            formview_supervision_with_chw_confirmation._id AS chw_site_uuid,
            formview_supervision_with_chw_confirmation.name AS chw_site,
            formview_supervision_with_chw_confirmation.contact__id AS chw_contact_id,
            formview_supervision_with_chw_confirmation.contact_name AS chw_contact_name,
            formview_supervision_with_chw_confirmation.place_id,
            formview_supervision_with_chw_confirmation.place_name,
            formview_supervision_with_chw_confirmation.reported AS reported_at,
            NULL::timestamp with time zone AS planned_visit_at,
            NULL::timestamp with time zone AS rescheduled_visit_at,
            formview_supervision_with_chw_confirmation.has_visit_been_made,
            formview_supervision_with_chw_confirmation.why_visit_not_done,
            formview_supervision_with_chw_confirmation.reason_visit_not_done,
            formview_supervision_with_chw_confirmation.have_schedule_another_visit,
            NULL::text AS steps_been_done,
            NULL::text AS is_rescheduled,
            NULL::text AS next_visit_date,
            NULL::text AS s_patient_assessed,
            NULL::text AS s_tdr_done,
            NULL::text AS rdt_correctly_carried_out,
            NULL::numeric AS final_score
           FROM formview_supervision_with_chw_confirmation
        UNION ALL
         SELECT formview_supervision_without_chw_confirmation.uuid,
            'supervision_without_chw_confirmation'::text AS form_name,
            'visit_without_chw_confirmation'::text AS activity_code,
            'Confirmation supervision sans ASC'::text AS activity_label,
            40 AS activity_order,
            formview_supervision_without_chw_confirmation.reported_by,
            formview_supervision_without_chw_confirmation.reported_by_parent AS supervisor_area_uuid,
            formview_supervision_without_chw_confirmation.source,
            formview_supervision_without_chw_confirmation.source_id,
            formview_supervision_without_chw_confirmation._id AS chw_site_uuid,
            formview_supervision_without_chw_confirmation.name AS chw_site,
            formview_supervision_without_chw_confirmation.contact__id AS chw_contact_id,
            formview_supervision_without_chw_confirmation.contact_name AS chw_contact_name,
            formview_supervision_without_chw_confirmation.place_id,
            formview_supervision_without_chw_confirmation.place_name,
            formview_supervision_without_chw_confirmation.reported AS reported_at,
            NULL::timestamp with time zone AS planned_visit_at,
            NULL::timestamp with time zone AS rescheduled_visit_at,
            formview_supervision_without_chw_confirmation.has_visit_been_made,
            formview_supervision_without_chw_confirmation.why_visit_not_done,
            formview_supervision_without_chw_confirmation.reason_visit_not_done,
            formview_supervision_without_chw_confirmation.have_schedule_another_visit,
            NULL::text AS steps_been_done,
            NULL::text AS is_rescheduled,
            NULL::text AS next_visit_date,
            NULL::text AS s_patient_assessed,
            NULL::text AS s_tdr_done,
            NULL::text AS rdt_correctly_carried_out,
            NULL::numeric AS final_score
           FROM formview_supervision_without_chw_confirmation
        UNION ALL
         SELECT formview_visit_chw_site.uuid,
            'visit_chw_site'::text AS form_name,
            'visit_with_chw'::text AS activity_code,
            'Visite site ASC'::text AS activity_label,
            50 AS activity_order,
            formview_visit_chw_site.reported_by,
            formview_visit_chw_site.reported_by_parent AS supervisor_area_uuid,
            formview_visit_chw_site.source,
            formview_visit_chw_site.source_id,
            formview_visit_chw_site._id AS chw_site_uuid,
            formview_visit_chw_site.name AS chw_site,
            formview_visit_chw_site.contact__id AS chw_contact_id,
            formview_visit_chw_site.contact_name AS chw_contact_name,
            formview_visit_chw_site.place_id,
            formview_visit_chw_site.place_name,
            formview_visit_chw_site.reported AS reported_at,
            NULL::timestamp with time zone AS planned_visit_at,
            NULL::timestamp with time zone AS rescheduled_visit_at,
            NULL::text AS has_visit_been_made,
            NULL::text AS why_visit_not_done,
            NULL::text AS reason_visit_not_done,
            NULL::text AS have_schedule_another_visit,
            NULL::text AS steps_been_done,
            NULL::text AS is_rescheduled,
            NULL::text AS next_visit_date,
            formview_visit_chw_site.s_patient_assessed,
            formview_visit_chw_site.s_tdr_done,
                CASE
                    WHEN formview_visit_chw_site.s_tdr_done = 'yes'::text AND formview_visit_chw_site.s_tdr_indications = 'yes'::text AND formview_visit_chw_site.s_tdr_kit_assembled = 'yes'::text AND formview_visit_chw_site.s_tdr_peremption_date = 'yes'::text AND formview_visit_chw_site.s_tdr_peremption = 'no'::text AND formview_visit_chw_site.s_gloves = 'yes'::text AND formview_visit_chw_site.s_tdr_information = 'yes'::text AND formview_visit_chw_site.s_finger_disinfection = 'yes'::text AND formview_visit_chw_site.s_blood_quantity = 'one_pipette'::text AND formview_visit_chw_site.s_solvent_drops = 'yes'::text AND formview_visit_chw_site.s_needles_arranged = 'yes'::text AND formview_visit_chw_site.s_tdr_required_time_to_read = 'yes'::text AND formview_visit_chw_site.s_tdr_result_well_interpreted = 'yes'::text THEN 'yes'::text
                    ELSE 'no'::text
                END AS rdt_correctly_carried_out,
            NULLIF(regexp_replace(formview_visit_chw_site.final_score, '[^0-9.]+'::text, ''::text, 'g'::text), ''::text)::numeric AS final_score
           FROM formview_visit_chw_site
        UNION ALL
         SELECT formview_visit_community_without_chw.uuid,
            'visit_community_without_chw'::text AS form_name,
            'visit_without_chw'::text AS activity_code,
            'Visite communaute sans ASC'::text AS activity_label,
            60 AS activity_order,
            formview_visit_community_without_chw.reported_by,
            formview_visit_community_without_chw.reported_by_parent AS supervisor_area_uuid,
            formview_visit_community_without_chw.source,
            formview_visit_community_without_chw.source_id,
            formview_visit_community_without_chw._id AS chw_site_uuid,
            formview_visit_community_without_chw.name AS chw_site,
            formview_visit_community_without_chw.contact__id AS chw_contact_id,
            formview_visit_community_without_chw.contact_name AS chw_contact_name,
            formview_visit_community_without_chw.place_id,
            formview_visit_community_without_chw.place_name,
            formview_visit_community_without_chw.reported AS reported_at,
            NULL::timestamp with time zone AS planned_visit_at,
            NULL::timestamp with time zone AS rescheduled_visit_at,
            NULL::text AS has_visit_been_made,
            NULL::text AS why_visit_not_done,
            NULL::text AS reason_visit_not_done,
            NULL::text AS have_schedule_another_visit,
            NULL::text AS steps_been_done,
            NULL::text AS is_rescheduled,
            NULL::text AS next_visit_date,
            NULL::text AS s_patient_assessed,
            NULL::text AS s_tdr_done,
            NULL::text AS rdt_correctly_carried_out,
            NULL::numeric AS final_score
           FROM formview_visit_community_without_chw
        UNION ALL
         SELECT fif.uuid,
            'individual_feedback'::text AS form_name,
            'individual_feedback'::text AS activity_code,
            'Feedback individuel'::text AS activity_label,
            70 AS activity_order,
            fif.reported_by,
            fif.reported_by_parent AS supervisor_area_uuid,
            fif.source,
            fif.source_id,
            fif._id AS chw_site_uuid,
            fif.name AS chw_site,
            fif.contact__id AS chw_contact_id,
            fif.contact_name AS chw_contact_name,
            fif.place_id,
            fif.place_name,
            fif.reported AS reported_at,
            NULL::timestamp with time zone AS planned_visit_at,
            NULL::timestamp with time zone AS rescheduled_visit_at,
            NULL::text AS has_visit_been_made,
            NULL::text AS why_visit_not_done,
            NULL::text AS reason_visit_not_done,
            NULL::text AS have_schedule_another_visit,
            NULL::text AS steps_been_done,
            to_jsonb(fif.*) ->> 'is_rescheduled'::text AS is_rescheduled,
            to_jsonb(fif.*) ->> 'next_visit_date'::text AS next_visit_date,
            NULL::text AS s_patient_assessed,
            NULL::text AS s_tdr_done,
            NULL::text AS rdt_correctly_carried_out,
            NULL::numeric AS final_score
           FROM formview_individual_feedback fif
        UNION ALL
         SELECT formview_individual_feedback_confirmation.uuid,
            'individual_feedback_confirmation'::text AS form_name,
            'individual_feedback_confirmation'::text AS activity_code,
            'Confirmation feedback individuel'::text AS activity_label,
            80 AS activity_order,
            formview_individual_feedback_confirmation.reported_by,
            formview_individual_feedback_confirmation.reported_by_parent AS supervisor_area_uuid,
            formview_individual_feedback_confirmation.source,
            formview_individual_feedback_confirmation.source_id,
            formview_individual_feedback_confirmation._id AS chw_site_uuid,
            formview_individual_feedback_confirmation.name AS chw_site,
            formview_individual_feedback_confirmation.contact__id AS chw_contact_id,
            formview_individual_feedback_confirmation.contact_name AS chw_contact_name,
            NULL::text AS place_id,
            NULL::text AS place_name,
            formview_individual_feedback_confirmation.reported AS reported_at,
            NULL::timestamp with time zone AS planned_visit_at,
            NULL::timestamp with time zone AS rescheduled_visit_at,
            formview_individual_feedback_confirmation.has_visit_been_made,
            formview_individual_feedback_confirmation.why_visit_not_done,
            formview_individual_feedback_confirmation.reason_visit_not_done,
            formview_individual_feedback_confirmation.have_schedule_another_visit,
            NULL::text AS steps_been_done,
            NULL::text AS is_rescheduled,
            NULL::text AS next_visit_date,
            NULL::text AS s_patient_assessed,
            NULL::text AS s_tdr_done,
            NULL::text AS rdt_correctly_carried_out,
            NULL::numeric AS final_score
           FROM formview_individual_feedback_confirmation
        UNION ALL
         SELECT formview_location_gps.uuid,
            'location_gps'::text AS form_name,
            'location_gps'::text AS activity_code,
            'Geolocalisation site ASC'::text AS activity_label,
            90 AS activity_order,
            formview_location_gps.reported_by,
            formview_location_gps.reported_by_parent AS supervisor_area_uuid,
            formview_location_gps.source,
            formview_location_gps.source_id,
            formview_location_gps._id AS chw_site_uuid,
            formview_location_gps.name AS chw_site,
            formview_location_gps.contact__id AS chw_contact_id,
            formview_location_gps.contact_name AS chw_contact_name,
            formview_location_gps.place_id,
            formview_location_gps.place_name,
            formview_location_gps.reported AS reported_at,
            NULL::timestamp with time zone AS planned_visit_at,
            NULL::timestamp with time zone AS rescheduled_visit_at,
            NULL::text AS has_visit_been_made,
            NULL::text AS why_visit_not_done,
            NULL::text AS reason_visit_not_done,
            NULL::text AS have_schedule_another_visit,
            NULL::text AS steps_been_done,
            NULL::text AS is_rescheduled,
            NULL::text AS next_visit_date,
            NULL::text AS s_patient_assessed,
            NULL::text AS s_tdr_done,
            NULL::text AS rdt_correctly_carried_out,
            NULL::numeric AS final_score
           FROM formview_location_gps
        )
 SELECT concat(e.form_name, ':', e.uuid) AS event_uid,
    e.uuid AS report_uuid,
    e.form_name,
    e.activity_code,
    e.activity_label,
    e.activity_order,
    e.reported_at,
    e.reported_at::date AS reported_date,
    date_trunc('month'::text, e.reported_at)::date AS reported_month,
    to_char(e.reported_at, 'YYYY-MM'::text) AS period,
    to_char(e.reported_at, 'YYYYMM'::text) AS period_yyyymm,
    date_part('year'::text, e.reported_at)::integer AS year,
    date_part('quarter'::text, e.reported_at)::integer AS quarter,
    date_part('month'::text, e.reported_at)::integer AS month_number,
    date_part('year'::text, date_trunc('month'::text, e.reported_at))::integer AS reported_year,
    get_quarterly_period(date_trunc('month'::text, e.reported_at)::date) AS reported_quarter,
    get_semester_period(date_trunc('month'::text, e.reported_at)::date) AS reported_semester,
    get_month_year_fr(date_trunc('month'::text, e.reported_at)::date) AS reported_month_fr,
    e.planned_visit_at,
    e.rescheduled_visit_at,
    COALESCE(p.central_uuid, sp.central_uuid) AS central_uuid,
    COALESCE(p.central, sp.central) AS central,
    COALESCE(p.region_uuid, sp.region_uuid) AS region_uuid,
    COALESCE(p.region, sp.region) AS region,
    COALESCE(p.district_uuid, sp.district_uuid) AS district_uuid,
    COALESCE(p.district, sp.district) AS district,
    COALESCE(p.health_area_uuid, sp.health_area_uuid) AS health_area_uuid,
    COALESCE(p.health_area, sp.health_area) AS health_area,
    COALESCE(p.supervisor_area_uuid, e.supervisor_area_uuid, sp.supervisor_area_uuid) AS supervisor_area_uuid,
    COALESCE(p.supervisor_area, sp.supervisor_area) AS supervisor_area,
    e.reported_by AS supervisor_contact_id,
    a.supervisor_key,
    a.supervisor_uuid,
    a.supervisor_username,
    a.supervisor_name,
    a.supervisor_first_name,
    a.supervisor_last_name,
    a.supervisor_phone,
    a.supervisor_email,
    a.supervisor_sex,
    a.assignment_status,
    a.assignment_source,
    e.chw_site_uuid,
    COALESCE(p.chw_site, e.chw_site, e.place_name) AS chw_site,
    e.chw_contact_id,
    e.chw_contact_name,
    e.source,
    e.source_id,
    e.place_id,
    e.place_name,
    e.has_visit_been_made,
    e.why_visit_not_done,
    e.reason_visit_not_done,
    e.have_schedule_another_visit,
    e.steps_been_done,
    e.is_rescheduled,
    e.next_visit_date,
        CASE
            WHEN e.form_name = 'supervision_calendar'::text THEN 1
            ELSE 0
        END AS is_planned_visit_report,
        CASE
            WHEN e.form_name = 'supervision_visit_realization'::text THEN 1
            ELSE 0
        END AS is_visit_realization_report,
        CASE
            WHEN e.form_name = 'visit_chw_site'::text THEN 1
            ELSE 0
        END AS is_visit_with_chw_report,
        CASE
            WHEN e.form_name = 'visit_community_without_chw'::text THEN 1
            ELSE 0
        END AS is_visit_without_chw_report,
        CASE
            WHEN e.form_name = 'individual_feedback'::text THEN 1
            ELSE 0
        END AS is_individual_feedback_report,
        CASE
            WHEN e.form_name = 'individual_feedback_confirmation'::text THEN 1
            ELSE 0
        END AS is_individual_feedback_confirmation_report,
        CASE
            WHEN e.form_name = 'location_gps'::text THEN 1
            ELSE 0
        END AS is_location_gps_report,
        CASE
            WHEN e.form_name = ANY (ARRAY['visit_chw_site'::text, 'visit_community_without_chw'::text, 'individual_feedback'::text, 'location_gps'::text]) THEN 1
            WHEN e.has_visit_been_made = 'yes'::text THEN 1
            ELSE 0
        END AS is_visit_done,
        CASE
            WHEN e.steps_been_done = 'yes'::text THEN 1
            ELSE 0
        END AS is_steps_done,
        CASE
            WHEN e.have_schedule_another_visit = 'yes'::text OR e.is_rescheduled = 'yes'::text THEN 1
            ELSE 0
        END AS is_rescheduled_report,
        CASE
            WHEN e.has_visit_been_made = 'no'::text AND e.why_visit_not_done = 'supervisor_unavailable'::text THEN 1
            ELSE 0
        END AS is_not_done_supervisor_unavailable,
        CASE
            WHEN e.s_patient_assessed = 'yes'::text THEN 1
            ELSE 0
        END AS is_patient_assessed,
        CASE
            WHEN e.s_tdr_done = 'yes'::text THEN 1
            ELSE 0
        END AS is_rdt_done,
        CASE
            WHEN e.rdt_correctly_carried_out = 'yes'::text THEN 1
            ELSE 0
        END AS is_rdt_correctly_done,
    e.final_score,
        CASE
            WHEN e.final_score >= 80::numeric THEN 1
            ELSE 0
        END AS has_acceptable_score
   FROM raw_events e
     CROSS JOIN params period_params
     LEFT JOIN places p ON p.chw_site_uuid = e.chw_site_uuid
     LEFT JOIN supervisor_places sp ON sp.supervisor_area_uuid = e.supervisor_area_uuid
     LEFT JOIN mv_superset_sd_zone_assignments a ON a.supervisor_area_uuid = COALESCE(p.supervisor_area_uuid, e.supervisor_area_uuid)
  WHERE e.reported_at IS NOT NULL AND e.reported_at::date >= period_params.start_month AND e.reported_at::date < (period_params.end_month + '1 mon'::interval);