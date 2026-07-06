@echo off
rem Installs a Windows Startup launcher so VoiceFlow starts at every logon.
rem Run this AFTER the app has been run at least once (so .venv exists).
rem Uninstall: delete the VoiceFlow.vbs file this creates.

if not exist "%~dp0.venv\Scripts\pythonw.exe" (
    echo .venv not found. Run "uv run voiceflow" once first, then re-run this.
    pause
    exit /b 1
)

set "TARGET=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\VoiceFlow.vbs"
> "%TARGET%" echo ' Auto-starts VoiceFlow dictation at logon - delete this file to disable.
>> "%TARGET%" echo Set sh = CreateObject("Wscript.Shell")
>> "%TARGET%" echo sh.CurrentDirectory = "%~dp0"
>> "%TARGET%" echo sh.Run """%~dp0.venv\Scripts\pythonw.exe"" -m voiceflow", 0, False

echo Installed: %TARGET%
echo VoiceFlow will now start automatically at logon.
pause
