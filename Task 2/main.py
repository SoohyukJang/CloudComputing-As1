# [1] Google LLC, "BigQuery client libraries," Google Cloud Documentation.
#     Available: https://cloud.google.com/bigquery/docs/reference/libraries

from flask import Flask, render_template
from google.cloud import bigquery

app = Flask(__name__)
client = bigquery.Client()

TRADE = "`project-a899d2ee-9a1f-43f4-9dc.trade_data.gsquarterlySeptember20`"
COUNTRIES = "`project-a899d2ee-9a1f-43f4-9dc.trade_data.country_classification`"
SERVICES = "`project-a899d2ee-9a1f-43f4-9dc.trade_data.services_classification`"

Q1_SQL = f"""
SELECT time_ref, SUM(SAFE_CAST(value AS FLOAT64)) AS trade_value
FROM {TRADE}
WHERE account IN ('Imports', 'Exports')
GROUP BY time_ref
ORDER BY trade_value DESC
LIMIT 10
"""

Q2_SQL = f"""
SELECT
  c.country_label,
  SUM(IF(g.account = 'Imports', SAFE_CAST(g.value AS FLOAT64), -SAFE_CAST(g.value AS FLOAT64))) AS trade_deficit_value
FROM {TRADE} g
JOIN {COUNTRIES} c ON g.country_code = c.country_code
WHERE g.product_type = 'Goods' AND g.time_ref BETWEEN '201301' AND '201512' AND g.status = 'F'
GROUP BY c.country_label
ORDER BY trade_deficit_value DESC
LIMIT 40
"""

Q3_SQL = f"""
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
  FROM {TRADE} g
  JOIN {COUNTRIES} c ON g.country_code = c.country_code
  WHERE g.product_type = 'Goods' AND g.time_ref BETWEEN '201301' AND '201512' AND g.status = 'F'
  GROUP BY c.country_code
  ORDER BY SUM(IF(g.account = 'Imports', SAFE_CAST(g.value AS FLOAT64), -SAFE_CAST(g.value AS FLOAT64))) DESC
  LIMIT 40
)
SELECT
  s.service_label,
  SUM(IF(g.account = 'Exports', SAFE_CAST(g.value AS FLOAT64), -SAFE_CAST(g.value AS FLOAT64))) AS trade_surplus_value
FROM {TRADE} g
JOIN {SERVICES} s ON g.code = s.code
WHERE g.product_type = 'Services'
  AND g.time_ref IN (SELECT time_ref FROM top_periods)
  AND g.country_code IN (SELECT country_code FROM top_countries)
GROUP BY s.service_label
ORDER BY trade_surplus_value DESC
LIMIT 25
"""


@app.route("/")
def index():
    q1_rows = list(client.query(Q1_SQL).result())
    q2_rows = list(client.query(Q2_SQL).result())
    q3_rows = list(client.query(Q3_SQL).result())
    return render_template("index.html", q1_rows=q1_rows, q2_rows=q2_rows, q3_rows=q3_rows)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)
