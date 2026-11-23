# Finance plugin path adapter

The deployed `finance-tools` plugin expects scripts below
`US-market/findata-toolkit/` and `China-market/findata-toolkit-cn/`, whereas
installed global skills live directly below `~/.fastclaw/skills/`. These
minimal entrypoints execute the installed skill scripts without copying or
modifying them. The plugin's `finskillsPath` should point to this directory.

This adapter is for online tools. Evaluation fixtures remain separate. The
Python interpreter configured as `pythonBin` must have the dependencies from
both installed FinData Toolkit `requirements.txt` files.
