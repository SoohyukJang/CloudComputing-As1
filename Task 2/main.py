# [1] Google LLC, "BigQuery client libraries," Google Cloud Documentation.
#     Available: https://cloud.google.com/bigquery/docs/reference/libraries

from flask import Flask, render_template
from google.cloud import bigquery

app = Flask(__name__)
client = bigquery.Client()

# Deployed separately from Task 1 (rmit-cloud-2026) so the two App Engine
# apps don't fight over the same project's "default" service.
DATASET = "project-a899d2ee-9a1f-43f4-9dc.trade_data"

TRADE = f"`{DATASET}.gsquarterlySeptember20`"
COUNTRY = f"`{DATASET}.country_classification`"
SERVICE = f"`{DATASET}.services_classification`"  # join key column is `code`, not country_code

# time_ref and value are stored as strings in this dataset, hence SAFE_CAST throughout.
Q1 = f"""
SELECT
  time_ref,
  SUM(SAFE_CAST(value AS FLOAT64)) AS trade_value
FROM {TRADE}
WHERE account IN ('Imports', 'Exports')
GROUP BY time_ref
ORDER BY trade_value DESC
LIMIT 10
"""

Q2 = f"""
SELECT
  c.country_label AS country_label,
  t.product_type  AS product_type,
  SUM(CASE WHEN t.account = 'Imports' THEN SAFE_CAST(t.value AS FLOAT64) ELSE 0 END)
    - SUM(CASE WHEN t.account = 'Exports' THEN SAFE_CAST(t.value AS FLOAT64) ELSE 0 END) AS trade_deficit_value,
  t.status AS status
FROM {TRADE} t
JOIN {COUNTRY} c
  ON t.country_code = c.country_code
WHERE t.product_type = 'Goods'
  AND t.status = 'F'
  AND CAST(SUBSTR(CAST(t.time_ref AS STRING), 1, 4) AS INT64) BETWEEN 2013 AND 2015
GROUP BY country_label, product_type, status
ORDER BY trade_deficit_value DESC
LIMIT 40
"""

Q3 = f"""
WITH top_periods AS (
  SELECT time_ref
  FROM {TRADE}
  WHERE account IN ('Imports', 'Exports')
  GROUP BY time_ref
  ORDER BY SUM(SAFE_CAST(value AS FLOAT64)) DESC
  LIMIT 10
),
top_countries AS (
  SELECT c.country_code
  FROM {TRADE} t
  JOIN {COUNTRY} c ON t.country_code = c.country_code
  WHERE t.product_type = 'Goods'
    AND t.status = 'F'
    AND CAST(SUBSTR(CAST(t.time_ref AS STRING), 1, 4) AS INT64) BETWEEN 2013 AND 2015
  GROUP BY c.country_code
  ORDER BY
    SUM(CASE WHEN t.account = 'Imports' THEN SAFE_CAST(t.value AS FLOAT64) ELSE 0 END)
    - SUM(CASE WHEN t.account = 'Exports' THEN SAFE_CAST(t.value AS FLOAT64) ELSE 0 END) DESC
  LIMIT 40
)
SELECT
  s.service_label AS service_label,
  SUM(CASE WHEN t.account = 'Exports' THEN SAFE_CAST(t.value AS FLOAT64) ELSE 0 END)
    - SUM(CASE WHEN t.account = 'Imports' THEN SAFE_CAST(t.value AS FLOAT64) ELSE 0 END) AS trade_surplus_value
FROM {TRADE} t
JOIN {SERVICE} s ON t.code = s.code
WHERE t.product_type = 'Services'
  AND t.time_ref IN (SELECT time_ref FROM top_periods)
  AND t.country_code IN (SELECT country_code FROM top_countries)
GROUP BY service_label
ORDER BY trade_surplus_value DESC
LIMIT 25
"""


def run(query):
    return list(client.query(query).result())


@app.route("/")
def index():
    q1_rows = run(Q1)
    q2_rows = run(Q2)
    q3_rows = run(Q3)
    return render_template(
        "index.html",
        q1_rows=q1_rows,
        q2_rows=q2_rows,
        q3_rows=q3_rows,
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)