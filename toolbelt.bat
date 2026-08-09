@echo off
set "TOOLBELT_ROOT=%~dp0"
uv run --project "%TOOLBELT_ROOT:~0,-1%" "%TOOLBELT_ROOT%toolbelt.py" %*
