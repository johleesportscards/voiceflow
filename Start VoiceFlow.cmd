@echo off
rem Manual launcher with visible console (for debugging). Normally VoiceFlow
rem auto-starts at logon via Startup\VoiceFlow.vbs; a second launch exits
rem immediately thanks to the single-instance guard.
cd /d "%~dp0"
uv run voiceflow
pause
