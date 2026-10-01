-- Business question: of the deals that reached each stage, how many made it to the next one,
-- and at which stage do most deals die?
-- Only closed deals are counted: an open deal has not had the chance to pass or fail yet,
-- and including it would make every stage look leakier than it is.

WITH closed AS (
    SELECT deal_id, is_won, last_open_stage
    FROM deals
    WHERE is_closed
),
reached AS (
    SELECT s.stage, s.stage_rank, count(DISTINCT s.deal_id) AS deals_reached
    FROM stage_spells s
    JOIN closed c USING (deal_id)
    GROUP BY s.stage, s.stage_rank
    UNION ALL
    SELECT 'Closed Won', 5, count(*) FROM closed WHERE is_won
),
died AS (
    SELECT last_open_stage AS stage, count(*) AS deals_lost_here
    FROM closed
    WHERE NOT is_won
    GROUP BY last_open_stage
)
SELECT r.stage,
       r.deals_reached,
       round(r.deals_reached / LAG(r.deals_reached) OVER (ORDER BY r.stage_rank), 3)
                                                              AS conversion_from_previous,
       round(r.deals_reached / first_value(r.deals_reached) OVER (ORDER BY r.stage_rank), 3)
                                                              AS conversion_from_start,
       coalesce(d.deals_lost_here, 0)                         AS deals_lost_here,
       round(coalesce(d.deals_lost_here, 0)
             / sum(d.deals_lost_here) OVER (), 3)             AS share_of_all_losses
FROM reached r
LEFT JOIN died d USING (stage)
ORDER BY r.stage_rank;
