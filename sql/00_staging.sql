-- Staging: load each CSV once into a table, plus the two derived tables every other query uses.
-- {data_dir} and {snapshot} are filled in by the runner.
--
-- stage_spells turns the stage history into "how long did the deal sit in each stage".
-- A stage ends when the next row starts (LEAD), not at exited_date: that is how a CRM user
-- reads it, and it keeps the time between the last open stage and the close inside the
-- Negotiation stage instead of losing it.

CREATE OR REPLACE TABLE deals AS
SELECT d.*,
       c.sector, c.region, c.employees, c.size_segment,
       coalesce(p.partner_type, 'No partner') AS partner_type,
       p.partner_name
FROM read_csv_auto('{data_dir}/fact_deals.csv') d
JOIN read_csv_auto('{data_dir}/dim_company.csv') c USING (company_id)
LEFT JOIN read_csv_auto('{data_dir}/dim_partner.csv') p USING (partner_id);

CREATE OR REPLACE TABLE partners AS
SELECT * FROM read_csv_auto('{data_dir}/dim_partner.csv');

CREATE OR REPLACE TABLE stage_history AS
SELECT * FROM read_csv_auto('{data_dir}/fact_stage_history.csv');

CREATE OR REPLACE VIEW stage_order AS
SELECT * FROM (VALUES ('Discovery', 1), ('Qualified', 2), ('Proposal', 3),
                      ('Negotiation', 4), ('Closed Won', 5), ('Closed Lost', 5)) t(stage, stage_rank);

CREATE OR REPLACE TABLE stage_spells AS
WITH ordered AS (
    SELECT h.deal_id, h.stage, o.stage_rank, h.entered_date,
           LEAD(h.entered_date) OVER (PARTITION BY h.deal_id ORDER BY o.stage_rank) AS left_date
    FROM stage_history h
    JOIN stage_order o USING (stage)
)
SELECT deal_id, stage, stage_rank, entered_date, left_date,
       coalesce(left_date, DATE '{snapshot}') - entered_date AS days_in_stage,
       left_date IS NULL                                     AS is_current
FROM ordered
WHERE stage NOT LIKE 'Closed%';
