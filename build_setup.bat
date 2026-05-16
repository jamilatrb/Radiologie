@echo off
setlocal

cd /d "%~dp0"

echo.
echo ==========================================
echo  Construction de l'installateur Windows
echo ==========================================
echo.

call build_exe.bat
if errorlevel 1 (
    echo [ERREUR] La construction du .exe a echoue.
    exit /b 1
)

set "ISCC_EXE="

for %%I in (iscc.exe) do if not "%%~$PATH:I"=="" set "ISCC_EXE=%%~$PATH:I"
if not defined ISCC_EXE if exist "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC_EXE if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC_EXE if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%ProgramFiles%\Inno Setup 6\ISCC.exe"

if not defined ISCC_EXE (
    echo [ERREUR] Inno Setup n'est pas installe.
    echo Installez Inno Setup 6 puis relancez ce script.
    echo Fichier attendu : ISCC.exe
    exit /b 1
)

echo Generation de l'installateur...
"%ISCC_EXE%" "setup_inno.iss"

if errorlevel 1 (
    echo [ERREUR] La creation du setup a echoue.
    exit /b 1
)

echo.
echo [OK] L'installateur est pret :
echo     %cd%\installer\Setup_GestionRadiologie.exe
echo.
echo Vous pouvez donner ce fichier au client.
echo.

endlocal
