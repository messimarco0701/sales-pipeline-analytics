-- Business question: for the deals created in each month, how many were eventually won?
-- Reading cohorts by creation month separates "we are creating worse deals" from
-- "recent deals simply have not closed yet". The open share column says how mature a cohort is.

SELECT date_trunc('month', created_date)::DATE                   AS cohort_month,
       count(*)                                                   AS deals_created,
       count(*) FILTER (WHERE is_closed)                          AS closed,
       count(*) FILTER (WHERE is_won)                             AS won,
       round(count(*) FILTER (WHERE NOT is_closed) / count(*), 3) AS open_share,
       round(count(*) FILTER (WHERE is_won)
             / nullif(count(*) FILTER (WHERE is_closed), 0), 3)   AS win_rate_closed,
       round(count(*) FILTER (WHERE is_won) / count(*), 3)        AS win_rate_all_created,
       coalesce(sum(amount) FILTER (WHERE is_won), 0)             AS bookings
FROM deals
GROUP BY ALL
ORDER BY cohort_month;
