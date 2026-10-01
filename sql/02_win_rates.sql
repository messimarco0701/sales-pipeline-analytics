-- Business question: which channels, segments, products and deal types convert best,
-- and is the difference big enough to trust given how many deals sit behind each number?
-- Win rate is won / closed. The 95% Wilson interval is computed here in SQL: unlike the
-- textbook p +/- 1.96*se it behaves well with small samples and rates near 0 or 1.
-- Deal size quartiles use NTILE over the amount of closed deals.

WITH closed AS (
    SELECT *, NTILE(4) OVER (ORDER BY amount) AS amount_quartile
    FROM deals
    WHERE is_closed
),
long_format AS (
    SELECT 'channel' AS dimension, channel AS value, is_won FROM closed
    UNION ALL SELECT 'size_segment',    size_segment,         is_won FROM closed
    UNION ALL SELECT 'product',         product,              is_won FROM closed
    UNION ALL SELECT 'deal_type',       deal_type,            is_won FROM closed
    UNION ALL SELECT 'amount_quartile', 'Q' || amount_quartile, is_won FROM closed
),
counts AS (
    SELECT dimension, value,
           count(*)                       AS closed_deals,
           count(*) FILTER (WHERE is_won) AS won_deals
    FROM long_format
    GROUP BY dimension, value
),
rates AS (
    SELECT *, won_deals / closed_deals AS p, 1.96 AS z
    FROM counts
)
SELECT dimension, value, closed_deals, won_deals,
       round(p, 3) AS win_rate,
       round((p + z*z / (2*closed_deals)
              - z * sqrt(p*(1-p) / closed_deals + z*z / (4*closed_deals*closed_deals)))
             / (1 + z*z / closed_deals), 3) AS ci_low,
       round((p + z*z / (2*closed_deals)
              + z * sqrt(p*(1-p) / closed_deals + z*z / (4*closed_deals*closed_deals)))
             / (1 + z*z / closed_deals), 3) AS ci_high
FROM rates
ORDER BY dimension, win_rate DESC;
