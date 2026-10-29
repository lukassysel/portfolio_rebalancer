"""Write the OpenAPI schema to web/openapi.json (input for the generated TypeScript types)."""

import json
from pathlib import Path

from .app import app

if __name__ == "__main__":
    out = Path(__file__).resolve().parents[2] / "web" / "openapi.json"
    out.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=1))
    print(f"wrote {out}")
