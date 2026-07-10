# [1] Google LLC, "BigQuery client libraries," Google Cloud Documentation.
#     Available: https://cloud.google.com/bigquery/docs/reference/libraries

from flask import Flask, render_template
from google.cloud import bigquery

app = Flask(__name__)
client = bigquery.Client()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)
