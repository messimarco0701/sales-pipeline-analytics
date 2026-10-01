-- Business question: is the mix of channels shifting? Share of deals created per quarter
-- by channel, with the share computed as a window over the quarter's total.

WITH by_quarter AS (
    SELECT date_trunc('quarter', created_date)::DATE AS quarter_start,
           channel,
           count(*) AS deals_created
    FROM deals
    GROUP BY ALL
)
SELECT quarter_start, channel, deals_created,
       round(deals_created / sum(deals_created) OVER (PARTITION BY quarter_start), 3)
           AS share_of_quarter
FROM by_quarter
ORDER BY quarter_start, channel;
