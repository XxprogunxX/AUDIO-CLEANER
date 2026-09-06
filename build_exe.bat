@echo off
setlocal
pushd "%~dp0"
echo Instalando dependencias fijadas...
python -m pip install -r requirements-lock.txt
if errorlevel 1 goto failed
echo Compilando aplicacion con sus dependencias de audio...
python -m PyInstaller --clean --noconfirm build_installer.spec
if errorlevel 1 goto failed
python scripts\check_exe_binaries.py
if errorlevel 1 goto failed
echo Compilacion verificada: dist\AudioDuplicateDetector.exe
popd
exit /b 0
:failed
echo ERROR: La compilacion o la verificacion fallo. No distribuir este resultado.
popd
exit /b 1
