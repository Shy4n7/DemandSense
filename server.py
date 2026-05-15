"""
server.py — Single Flask app that mounts all API routes.

Used for Docker / self-hosted deployment (Oracle Cloud, Render, etc.).
Vercel uses the individual api/*.py files instead.

Usage:
    gunicorn server:app --bind 0.0.0.0:8000 --workers 2 --timeout 120
    python server.py  (dev)
"""

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from flask import Flask

# Import the individual Flask apps and re-register their routes
# on a single combined app using blueprints.
from api.products   import app as products_app
from api.forecast   import app as forecast_app
from api.anomalies  import app as anomalies_app
from api.importance import app as importance_app
from api.inventory  import app as inventory_app
from api.simulation import app as simulation_app

app = Flask(__name__)

# Merge all routes from each sub-app into the combined app
for sub_app in (
    products_app,
    forecast_app,
    anomalies_app,
    importance_app,
    inventory_app,
    simulation_app,
):
    for rule in sub_app.url_map.iter_rules():
        # Skip the built-in static/favicon routes
        if rule.endpoint == "static":
            continue
        view_func = sub_app.view_functions[rule.endpoint]
        # Avoid duplicate endpoint names across sub-apps
        endpoint = f"{sub_app.name}.{rule.endpoint}"
        app.add_url_rule(
            str(rule),
            endpoint=endpoint,
            view_func=view_func,
            methods=rule.methods,
        )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
