-- Business question: are we growing, and by how much?
-- 2026 only runs to the end of September, so a full year cannot be compared with it.
-- Every year is cut to January-September (like for like) and compared with the previous one.

WITH ytd_created AS (
    SELECT year(created_date)                          AS year,
           count(*)                                    AS deals_created,
           count(*) FILTER (WHERE channel = 'Partner') AS partner_deals_created,
           sum(amount)                                 AS pipeline_created
    FROM deals
    WHERE month(created_date) <= 9
    GROUP BY ALL
),
ytd_won AS (
    SELECT year(close_date) AS year, count(*) AS deals_won, sum(amount) AS bookings
    FROM deals
    WHERE is_won AND month(close_date) <= 9
    GROUP BY ALL
)
SELECT year,
       'Jan-Sep' AS period,
       deals_created,
       round(deals_created / LAG(deals_created) OVER (ORDER BY year) - 1, 3) AS deals_created_yoy,
       pipeline_created,
       deals_won,
       bookings,
       round(bookings / LAG(bookings) OVER (ORDER BY year) - 1, 3)           AS bookings_yoy,
       round(partner_deals_created / deals_created, 3)                       AS partner_share
FROM ytd_created
LEFT JOIN ytd_won USING (year)
ORDER BY year;
