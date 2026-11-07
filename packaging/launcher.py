import os
from pathlib import Path
import traceback

if __name__ == "__main__":
    try:
        from app.main import main
        code = main()
    except Exception:
        report = os.environ.get("NOB_SMOKE_REPORT")
        if not report:
            raise
        Path(report).write_text(traceback.format_exc(), encoding="utf-8")
        code = 1
    raise SystemExit(code)
