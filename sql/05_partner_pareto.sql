-- Business question: how concentrated is the partner channel? How many partners bring 80%
-- of partner bookings, and how dependent are we on the top few?
-- Bookings = amount of Closed Won deals. Running totals with a window over the ranking.

WITH partner_bookings AS (
    SELECT p.partner_id, p.partner_name, p.partner_type,
           count(d.deal_id)                                   AS deals,
           count(d.deal_id) FILTER (WHERE d.is_won)           AS won_deals,
           coalesce(sum(d.amount) FILTER (WHERE d.is_won), 0) AS bookings
    FROM partners p
    LEFT JOIN deals d USING (partner_id)
    GROUP BY ALL
),
ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (ORDER BY bookings DESC, partner_id) AS rank,
           bookings / sum(bookings) OVER ()                       AS share,
           sum(bookings) OVER (ORDER BY bookings DESC, partner_id ROWS UNBOUNDED PRECEDING)
               / sum(bookings) OVER ()                            AS cumulative_share
    FROM partner_bookings
)
SELECT rank, partner_name, partner_type, deals, won_deals, bookings,
       round(share, 3)            AS share,
       round(cumulative_share, 3) AS cumulative_share,
       -- in the "80% group" if the partners ranked above had not reached 80% yet
       coalesce(LAG(cumulative_share) OVER (ORDER BY rank), 0) < 0.8 AS in_top_80pct
FROM ranked
ORDER BY rank;
