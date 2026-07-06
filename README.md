# VoiceFlow

Local, free dictation for Windows — a Wispr Flow-style tool that runs
entirely on your machine. Hold a hotkey anywhere, speak, release: your words
appear at the cursor, with live preview text while you talk.

- **Local speech-to-text** — Whisper large-v3-turbo on your GPU (99 languages,
  auto-detected per sentence, code-switching supported). No cloud, no
  subscription, no audio leaving your PC.
- **Fast** — a 20-second dictation transcribes in about a second on a
  mid-range NVIDIA card; short phrases feel instant.
- **Live preview** — a pill at the bottom of the screen shows your words as
  you speak, growing up to 7 rows.
- **Instant cleanup** — filler words (um, uh...) removed and custom
  dictionary applied in microseconds. Optional LLM cleanup (Claude API,
  Ollama, or LM Studio) if you want heavier rewriting.

## Requirements

- Windows 10/11
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (installs
  Python and all dependencies automatically)
- NVIDIA GPU recommended (any CUDA-capable card). Without one it falls back
  to CPU — works, but slower.
- ~2 GB disk for the speech model (downloaded automatically on first run)

Nothing else. No API keys, no LM Studio/Ollama, no accounts — those are
optional extras.

## Quick start

```powershell
git clone https://github.com/johleesportscards/voiceflow
cd voiceflow
uv run voiceflow
```

First run downloads the model (~1.6 GB); wait for the green mic icon in the
system tray. Then click into any text field, **hold Caps Lock, speak,
release** — your words paste at the cursor.

To start VoiceFlow automatically at every logon, run `install-autostart.cmd`
once (after the first run). Uninstall by deleting `VoiceFlow.vbs` from your
Startup folder.

## Hotkeys (default key: Caps Lock, change in config.yaml)

| Action | Result |
|---|---|
| Hold + speak + release | Transcribe and paste at cursor |
| Quick single tap | Normal caps-lock toggle (passed through, ~0.5 s delay) |
| Double-tap | Lock recording on (hands-free) |
| Single tap while locked | Stop and transcribe |
| Esc while recording | Cancel, discard audio |

Holding the key to talk never flips caps state — only a deliberate lone tap
does.

## Cleanup modes (tray menu > Cleanup, or `cleanup:` in config.yaml)

- **fast** (default) — instant: removes filler words, applies your custom
  dictionary. No LLM, no waiting.
- **auto / claude / ollama / lmstudio** — LLM cleanup: fixes grammar and
  punctuation, heavier rewriting. Claude needs `ANTHROPIC_API_KEY` set;
  Ollama/LM Studio need their local servers running. Adds seconds per
  dictation.
- **raw** — no cleanup at all.

## Config

Edit `config.yaml` and restart (tray > Quit, relaunch). Highlights:

- `hotkey` — any key name the `keyboard` library accepts (`f9`, `caps lock`,
  `right ctrl`...)
- `model` — `large-v3-turbo` (fast, recommended) or `large-v3` (max accuracy)
- `language` — `auto`, or pin a code like `en` / `ko`
- `filler_words` / `dictionary` — what fast cleanup removes and replaces
- `preview` / `preview_interval` — live preview on/off and refresh rate

Runtime logs: `voiceflow.log` next to the app.

## Known limitations

- Windows only (global hotkey, paste injection, and launchers are all
  Windows-specific).
- Hotkey and paste don't reach elevated (admin) windows unless VoiceFlow
  itself runs elevated.
- The live preview is a fast greedy pass — it may revise words while you
  talk. The pasted text comes from a higher-quality final pass.
- On CPU (no NVIDIA GPU), transcription is several times slower than the
  numbers above.

## License

[MIT](LICENSE)
