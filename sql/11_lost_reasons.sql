-- Business question: why do we lose deals, and does the reason change with the stage?
-- If early losses are "no response" and late ones are "price" and "competitor", the fix is
-- different: qualification early on, pricing and positioning late.
-- Conditional aggregation pivots the reasons into columns, as shares of the stage's losses.

SELECT last_open_stage AS stage_lost_at,
       count(*)        AS lost_deals,
       round(avg((lost_reason = 'No response')::INT), 3) AS no_response,
       round(avg((lost_reason = 'Not a fit')::INT), 3)   AS not_a_fit,
       round(avg((lost_reason = 'Timing')::INT), 3)      AS timing,
       round(avg((lost_reason = 'No budget')::INT), 3)   AS no_budget,
       round(avg((lost_reason = 'Price')::INT), 3)       AS price,
       round(avg((lost_reason = 'Competitor')::INT), 3)  AS competitor,
       sum(amount)                                       AS lost_amount
FROM deals
JOIN stage_order o ON o.stage = deals.last_open_stage
WHERE is_closed AND NOT is_won
GROUP BY last_open_stage, o.stage_rank
ORDER BY o.stage_rank;
