-- Business question: where do each quarter's bookings come from?
-- Split between deals that were already in the pipeline when the quarter started and deals
-- that were created and won inside the same quarter. The forecast treats the two separately.

WITH by_quarter AS (
    SELECT date_trunc('quarter', close_date)::DATE AS quarter_start,
           count(*)                                AS deals_won,
           sum(amount)                             AS bookings,
           coalesce(sum(amount) FILTER (WHERE created_date <  date_trunc('quarter', close_date)), 0)
                                                   AS from_open_pipeline,
           coalesce(sum(amount) FILTER (WHERE created_date >= date_trunc('quarter', close_date)), 0)
                                                   AS created_and_won_in_quarter
    FROM deals
    WHERE is_won
    GROUP BY ALL
)
SELECT *,
       round(bookings / LAG(bookings, 4) OVER (ORDER BY quarter_start) - 1, 3) AS bookings_yoy
FROM by_quarter
ORDER BY quarter_start;
