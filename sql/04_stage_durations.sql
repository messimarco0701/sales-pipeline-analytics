-- Business question: how long does a deal normally sit in each stage?
-- Based on completed stage spells only (the deal has already moved on or closed).
-- The p90 here is the threshold used later to flag open deals that are stuck.

SELECT stage,
       count(*)                           AS completed_spells,
       quantile_cont(days_in_stage, 0.50) AS p50_days,
       quantile_cont(days_in_stage, 0.75) AS p75_days,
       quantile_cont(days_in_stage, 0.90) AS p90_days
FROM stage_spells
WHERE NOT is_current
GROUP BY stage, stage_rank
ORDER BY stage_rank;
