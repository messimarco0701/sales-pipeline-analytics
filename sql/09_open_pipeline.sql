-- Business question: what is the open pipeline really worth at the snapshot date, and which
-- deals are stuck?
-- Each open deal is weighted by the historical probability that a deal which reached its
-- current stage ended up won (closed deals only). A deal is "stuck" when it has been in its
-- current stage longer than 90% of the deals of the same size that went through that stage.
-- The first version used one p90 per stage, and almost every stuck deal was Medium or Large:
-- big deals are slower at every stage, so the flag was mostly telling me the company size.

CREATE OR REPLACE TABLE open_pipeline AS
WITH closed_reach AS (
    SELECT s.stage, d.is_won
    FROM stage_spells s
    JOIN deals d USING (deal_id)
    WHERE d.is_closed
),
stage_win_prob AS (
    SELECT stage, count(*) AS closed_deals_reached,
           avg(is_won::INT) AS p_win_from_stage
    FROM closed_reach
    GROUP BY stage
),
stage_p90 AS (
    SELECT s.stage, d.size_segment, quantile_cont(s.days_in_stage, 0.90) AS p90_days
    FROM stage_spells s
    JOIN deals d USING (deal_id)
    WHERE NOT s.is_current
    GROUP BY ALL
),
current_spell AS (
    SELECT s.*
    FROM stage_spells s
    JOIN deals d USING (deal_id)
    WHERE NOT d.is_closed AND s.is_current
)
SELECT d.deal_id, d.deal_name, d.channel, d.deal_type, d.product, d.size_segment,
       d.created_date, c.stage, c.stage_rank, d.amount,
       round(w.p_win_from_stage, 3)                    AS p_win_from_stage,
       round(d.amount * w.p_win_from_stage, 0)         AS weighted_amount,
       c.days_in_stage,
       p.p90_days,
       c.days_in_stage > p.p90_days                     AS is_stuck,
       round(PERCENT_RANK() OVER (PARTITION BY c.stage ORDER BY c.days_in_stage), 2)
                                                       AS age_percentile_in_stage,
       DATE '{snapshot}' - d.created_date              AS deal_age_days
FROM current_spell c
JOIN deals d USING (deal_id)
JOIN stage_win_prob w ON w.stage = c.stage
JOIN stage_p90 p ON p.stage = c.stage AND p.size_segment = d.size_segment;

SELECT * FROM open_pipeline ORDER BY stage_rank DESC, weighted_amount DESC;
