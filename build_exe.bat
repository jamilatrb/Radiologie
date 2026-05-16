@echo off
setlocal

cd /d "%~dp0"

echo.
echo ==========================================
echo  Construction de l'executable Windows
echo ==========================================
echo.

if not exist "icon.ico" (
    echo [ERREUR] Le fichier icon.ico est introuvable dans ce dossier.
    exit /b 1
)

python -m pip show pyinstaller >nul 2>nul
if errorlevel 1 (
    echo Installation de PyInstaller...
    python -m pip install pyinstaller
    if errorlevel 1 (
        echo [ERREUR] Impossible d'installer PyInstaller.
        exit /b 1
    )
)

echo Generation du .exe...
python -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name "GestionRadiologie" ^
    --icon "icon.ico" ^
    --distpath "release" ^
    --workpath "build_pyinstaller" ^
    main.py

if errorlevel 1 (
    echo [ERREUR] La creation du .exe a echoue.
    exit /b 1
)

if exist "patients.db" copy /Y "patients.db" "release\\patients.db" >nul
if exist "README.txt" copy /Y "README.txt" "release\\README.txt" >nul
if exist "icon.ico" copy /Y "icon.ico" "release\\icon.ico" >nul

echo.
echo [OK] Le dossier client est pret :
echo     %cd%\\release
echo.
echo Fichiers livres :
echo - GestionRadiologie.exe
echo - patients.db
echo - README.txt
echo - icon.ico
echo.
echo Donnez tout le dossier release au client.
echo.

endlocal
