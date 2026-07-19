# [1] Google LLC, "BigQuery client libraries," Google Cloud Documentation.
#     Available: https://cloud.google.com/bigquery/docs/reference/libraries

from flask import Flask, render_template
from google.cloud import bigquery

app = Flask(__name__)
client = bigquery.Client()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)

# ---------------------------------------------------------------------------
# Dataset configuration.
# The three CSVs from a1.zip must be loaded into this dataset as tables named:
#   gsquarterlySeptember20, services_classification, country_classification
# Set DATASET to "project.dataset" (or just "dataset" if same project).
# ---------------------------------------------------------------------------
DATASET = "rmit-cloud-2026.a1"  # project.dataset

TRADE = f"`{DATASET}.gsquarterlySeptember20`"
COUNTRY = f"`{DATASET}.country_classification`"
SERVICE = f"`{DATASET}.services_classification`"  # join key column is `code`


# Q1: Top 10 time slots (year+month) by total trade value (imports + exports).
# time_ref in this dataset is a YYYYMM integer.
Q1 = f"""
SELECT
  time_ref,
  SUM(value) AS trade_value
FROM {TRADE}
WHERE account IN ('Imports', 'Exports')
GROUP BY time_ref
ORDER BY trade_value DESC
LIMIT 10
"""

# Q2: Top 40 countries by trade DEFICIT (imports - exports) of GOODS,
# years 2013-2015, status = 'F'. Deficit = imports - exports.
Q2 = f"""
SELECT
  c.country_label AS country_label,
  t.product_type  AS product_type,
  SUM(CASE WHEN t.account = 'Imports' THEN t.value ELSE 0 END)
    - SUM(CASE WHEN t.account = 'Exports' THEN t.value ELSE 0 END) AS trade_deficit_value,
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

# Q3: Top 25 SERVICES by trade SURPLUS (exports - imports), restricted to
# the Q1 time slots AND the Q2 countries.
Q3 = f"""
WITH top_periods AS (
  SELECT time_ref
  FROM {TRADE}
  WHERE account IN ('Imports', 'Exports')
  GROUP BY time_ref
  ORDER BY SUM(value) DESC
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
    SUM(CASE WHEN t.account = 'Imports' THEN t.value ELSE 0 END)
    - SUM(CASE WHEN t.account = 'Exports' THEN t.value ELSE 0 END) DESC
  LIMIT 40
)
SELECT
  s.service_label AS service_label,
  SUM(CASE WHEN t.account = 'Exports' THEN t.value ELSE 0 END)
    - SUM(CASE WHEN t.account = 'Imports' THEN t.value ELSE 0 END) AS trade_surplus_value
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