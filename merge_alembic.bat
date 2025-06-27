@echo off
set PYTHONPATH=%PYTHONPATH%;C:\Github\open-webui\backend
alembic -c backend/open_webui/alembic.ini merge -m "Merge heads for agents table" 3781e22d8b01 d488d31a738e