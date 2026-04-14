"""Registry export endpoint (Stage M).

Dumps all 4 global JSON stores into a single export payload.
"""

from __future__ import annotations

import json
import os
from datetime import datetime

from flask import jsonify

from .. import registry_bp
from ...config import Config


def _read_json(filename: str) -> dict:
    path = os.path.join(Config.UPLOAD_FOLDER, "projects", filename)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


@registry_bp.route("/export", methods=["GET"])
def export_registry():
    """Export all global registry data as a single JSON payload."""
    payload = {
        "version": 1,
        "exported_at": datetime.now().isoformat(),
        "concept_registry": _read_json("concept_registry.json"),
        "global_themes": _read_json("global_themes.json"),
        "evolution_log": _read_json("evolution_log.json"),
        "review_tasks": _read_json("review_tasks.json"),
    }
    return jsonify({"success": True, "data": payload})
