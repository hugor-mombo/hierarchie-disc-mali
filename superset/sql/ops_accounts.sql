-- Chaque seuil constitue une sélection indépendante. Filtre obligatoire à l'interface.
SELECT a.*,t.threshold_days,
       CASE WHEN last_personal_report IS NOT NULL THEN 'Rapport personnel ancien'
            WHEN last_site_report::date >= reference_date-t.threshold_days
              THEN 'Rapports du site sans attribution personnelle'
            ELSE 'Aucun rapport personnel retrouvé' END AS reason,
       CASE WHEN contact_status<>'Rattachement concordant'
              OR (last_personal_report IS NULL AND last_site_report::date >= reference_date-t.threshold_days)
            THEN 'À vérifier' ELSE 'À relancer' END AS action_status
FROM public.mv_asc_ops_accounts a
CROSS JOIN (VALUES (7),(14),(30)) t(threshold_days)
WHERE last_personal_report IS NULL OR days_without_report>=t.threshold_days
