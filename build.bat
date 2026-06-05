@echo off
echo Building Freight Daddy CRM desktop app...

pyinstaller --noconfirm --clean ^
  --name "FreightDaddyCRM" ^
  --onedir ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  launcher.py

echo.
echo Done! Your app is in the dist\FreightDaddyCRM\ folder.
echo Copy contacts.json, shipments.json, and config.json into that folder,
echo then double-click FreightDaddyCRM.exe to launch.
pause
