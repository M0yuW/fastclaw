from pathlib import Path
import runpy

runpy.run_path(str(Path.home() / ".fastclaw/skills/findata-toolkit/scripts/portfolio_analytics.py"), run_name="__main__")
