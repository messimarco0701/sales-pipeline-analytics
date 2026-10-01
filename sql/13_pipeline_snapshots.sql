-- Business question: what did the open pipeline look like at the end of each past quarter,
-- and how much of it was won in the following quarter?
-- This rebuilds history "as of" each quarter end, which is what makes an honest forecast
-- backtest possible: at each date we only use what was known on that date.
-- One row per (quarter end, deal open at that date). The last quarter end is the snapshot
-- itself, whose outcome is not known yet (won_next_quarter is NULL there).

WITH quarter_ends AS (
    SELECT (q + INTERVAL 3 MONTH - INTERVAL 1 DAY)::DATE AS as_of
    FROM generate_series(DATE '2024-01-01', DATE '{snapshot}' - INTERVAL 2 MONTH,
                         INTERVAL 3 MONTH) t(q)
),
open_at AS (
    SELECT q.as_of, d.deal_id, d.amount, d.is_won, d.close_date
    FROM quarter_ends q
    JOIN deals d
      ON d.created_date <= q.as_of
     AND (d.close_date IS NULL OR d.close_date > q.as_of)
),
stage_at AS (
    SELECT o.as_of, o.deal_id, h.stage,
           ROW_NUMBER() OVER (PARTITION BY o.as_of, o.deal_id
                              ORDER BY h.entered_date DESC, so.stage_rank DESC) AS rn
    FROM open_at o
    JOIN stage_history h ON h.deal_id = o.deal_id AND h.entered_date <= o.as_of
    JOIN stage_order so ON so.stage = h.stage
    WHERE h.stage NOT LIKE 'Closed%'
)
SELECT o.as_of, o.deal_id, s.stage, o.amount,
       CASE WHEN o.as_of = DATE '{snapshot}' THEN NULL
            ELSE o.is_won AND o.close_date <= (o.as_of + INTERVAL 3 MONTH)::DATE
       END AS won_next_quarter
FROM open_at o
JOIN stage_at s ON s.as_of = o.as_of AND s.deal_id = o.deal_id AND s.rn = 1
ORDER BY o.as_of, o.deal_id;
