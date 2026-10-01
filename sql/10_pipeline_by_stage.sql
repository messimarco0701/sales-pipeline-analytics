-- Business question: how is the open pipeline spread across stages, how much of it is real
-- once weighted, and how much is sitting idle?
-- Runs after 09_open_pipeline.sql, which builds the open_pipeline table.

SELECT stage,
       count(*)                                         AS open_deals,
       sum(amount)                                      AS pipeline_amount,
       any_value(p_win_from_stage)                      AS p_win_from_stage,
       sum(weighted_amount)                             AS weighted_amount,
       count(*) FILTER (WHERE is_stuck)                 AS stuck_deals,
       coalesce(sum(amount) FILTER (WHERE is_stuck), 0) AS stuck_amount,
       median(days_in_stage)                            AS median_days_in_stage
FROM open_pipeline
GROUP BY stage, stage_rank
ORDER BY stage_rank;
