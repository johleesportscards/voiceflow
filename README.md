# VoiceFlow

Local Wispr Flow-style dictation for Windows. Hold a hotkey anywhere, speak,
release — cleaned-up text appears at your cursor. Speech-to-text runs locally
on the GPU (faster-whisper large-v3, 99 languages); optional LLM cleanup via
Claude Haiku or a local model (Ollama or LM Studio).

## Run

```powershell
cd $env:USERPROFILE\Documents\Obsidian\Agent-Shared\voiceflow
uv run voiceflow
```

First run downloads the Whisper model (~3 GB). A green mic icon appears in the
system tray when ready.

## Hotkeys (default key: Caps Lock, change in config.yaml)

| Action | Result |
|---|---|
| Hold + speak + release | Transcribe and paste at cursor |
| Quick single tap | Normal caps-lock toggle (passed through, ~0.5 s delay) |
| Double-tap | Lock recording on (hands-free) |
| Single tap while locked | Stop and transcribe |
| Esc while recording | Cancel, discard audio |

With the Caps Lock hotkey, holding the key to talk never flips caps state —
only a deliberate lone tap does.

## Cleanup modes (tray menu > Cleanup, or `cleanup:` in config.yaml)

- **auto** — try Claude, then Ollama, then LM Studio, then raw. Never blocks
  dictation; any failure falls through within ~5 s.
- **claude** — Claude Haiku. Needs `ANTHROPIC_API_KEY` set in your environment.
- **ollama** — local model (default `qwen3:8b`) via Ollama at `localhost:11434`.
- **lmstudio** — local model via LM Studio's OpenAI-compatible server at
  `localhost:1234` (enable it in LM Studio > Developer > Start Server).
  `lmstudio_model` empty = first chat model listed; prefer a small model.
- **raw** — no cleanup, fastest.

## Config

Edit `config.yaml` (hotkey, model size, language, cleanup backend, paste vs
type injection, overlay). Restart the app to apply.

## Autostart (optional)

Create a shortcut to `uv run voiceflow` (working dir = this folder) in
`shell:startup`.

## Known limitations

- Hotkey and paste don't reach elevated (admin) windows unless VoiceFlow
  itself runs elevated.
- Transcription happens on key-release (1–2 s), not streamed while talking.
- VRAM: large-v3 uses ~3 GB; Ollama qwen3:8b another ~6 GB. Fine on a 16 GB
  card; on smaller cards set `model: distil-large-v3` or run Ollama on CPU.
