from pathlib import Path
import runpy

runpy.run_path(str(Path.home() / ".fastclaw/skills/findata-toolkit-cn/scripts/news_data.py"), run_name="__main__")
