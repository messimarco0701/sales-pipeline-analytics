-- Business question: how long does it take to close a deal, by customer size?
-- Cycle = days from the first stage to the closing row in the stage history.
-- Median, p75 and p90, because averages get dragged around by the few deals that sit for months.
-- Won deals are the cycle that matters for planning; the median of all closed deals is shown
-- next to it because lost deals tell you how long the team works on a deal before giving up.

WITH cycles AS (
    SELECT d.deal_id, d.size_segment, d.deal_type, d.is_won,
           max(h.entered_date) FILTER (WHERE h.stage LIKE 'Closed%')
         - min(h.entered_date) AS cycle_days
    FROM deals d
    JOIN stage_history h USING (deal_id)
    WHERE d.is_closed
    GROUP BY ALL
)
SELECT size_segment,
       count(*) FILTER (WHERE is_won)                         AS won_deals,
       quantile_cont(cycle_days, 0.50) FILTER (WHERE is_won)  AS won_p50,
       quantile_cont(cycle_days, 0.75) FILTER (WHERE is_won)  AS won_p75,
       quantile_cont(cycle_days, 0.90) FILTER (WHERE is_won)  AS won_p90,
       quantile_cont(cycle_days, 0.50)
           FILTER (WHERE is_won AND deal_type = 'New business') AS won_p50_new_business,
       quantile_cont(cycle_days, 0.50)
           FILTER (WHERE is_won AND deal_type = 'Upsell')       AS won_p50_upsell,
       count(*)                                               AS closed_deals,
       quantile_cont(cycle_days, 0.50)                        AS closed_p50
FROM cycles
GROUP BY size_segment
ORDER BY won_p50;
