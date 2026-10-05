@echo off
REM Builds ElectroPOS.exe on a Windows PC (run by double-click)
python -m pip install --upgrade pip
pip install kivy==2.3.0 pyinstaller
pyinstaller --onefile --windowed --name ElectroPOS --clean main.py
echo.
echo Done! Your app is: dist\ElectroPOS.exe
pause