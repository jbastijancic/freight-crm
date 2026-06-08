@echo off
echo Building Freight Daddy CRM desktop app...

pyinstaller --noconfirm --clean ^
  --name "FreightDaddyCRM" ^
  --onedir ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  --hidden-import=sqlalchemy.dialects.sqlite ^
  --hidden-import=flask_sqlalchemy ^
  launcher.py

echo.
echo Done! Your app is in the dist\FreightDaddyCRM\ folder.
echo Copy config.json into that folder, then double-click FreightDaddyCRM.exe to launch.
echo Your database (crm.db) will be created automatically on first run.
pause
