@echo off
cd /d "%~dp0"
echo Downloading Gemma 3 4B for local images and translation (about 3.3 GB).
ollama pull gemma3:4b
if errorlevel 1 goto fail
echo Ready. Start MAAN with START_ONLINE.bat and refresh the page.
goto end
:fail
echo Download failed. Open Ollama and check your internet connection, then retry.
:end
pause
