-- Business question: what does a normal year look like month by month?
-- Deals created and bookings won (by close month), one row per year and month, plus each
-- month's index against the average month of its own year, so the shape can be compared
-- across years with different volumes. 2026 stops at the snapshot (end of September).

WITH created AS (
    SELECT year(created_date) AS year, month(created_date) AS month, count(*) AS deals_created
    FROM deals
    GROUP BY ALL
),
won AS (
    SELECT year(close_date) AS year, month(close_date) AS month,
           count(*) AS deals_won, sum(amount) AS bookings
    FROM deals
    WHERE is_won
    GROUP BY ALL
)
SELECT year, month, deals_created,
       coalesce(deals_won, 0) AS deals_won,
       coalesce(bookings, 0)  AS bookings,
       round(deals_created / avg(deals_created) OVER (PARTITION BY year), 2) AS created_index
FROM created
LEFT JOIN won USING (year, month)
ORDER BY year, month;
