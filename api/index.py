"""
api/index.py — Single Lambda entrypoint for Vercel deployment.

Merges all API routes from the individual api/*.py Flask apps into one
combined Flask app. Vercel will bundle dependencies only once instead of
once per function file, reducing the total bundle from ~720 MB to ~120 MB.

This mirrors the pattern in server.py (used for Docker / self-hosted).
"""

import os
import sys

_API_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_API_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from flask import Flask

from api.products import app as products_app
from api.forecast import app as forecast_app
from api.anomalies import app as anomalies_app
from api.importance import app as importance_app
from api.inventory import app as inventory_app
from api.simulation import app as simulation_app

app = Flask(__name__)

for sub_app in (
    products_app,
    forecast_app,
    anomalies_app,
    importance_app,
    inventory_app,
    simulation_app,
):
    for rule in sub_app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        view_func = sub_app.view_functions[rule.endpoint]
        endpoint = f"{sub_app.name}.{rule.endpoint}"
        app.add_url_rule(
            str(rule),
            endpoint=endpoint,
            view_func=view_func,
            methods=rule.methods,
        )
