# TURTLE PATH GAME 🐢

Phone-first Kivy port of the original Turtle/Tkinter game.

## What changed
- Turtle/Tkinter UI replaced with Kivy Canvas/widgets.
- Touch-first controls plus desktop keyboard support.
- Original save JSON keys retained for compatibility.
- App-local save storage; no external-storage permission.
- Save failures are logged with timestamps and tracebacks.
- Blocking UI sleeps removed from the mobile UI path.
- Added beep, boop, and ding sounds.
- Added a small vector turtle icon.

## Desktop
```bash
python -m pip install kivy
python main.py
```

Controls: WASD or arrow keys. On phone, use the on-screen pad.

## Android
Install Buildozer on Linux/WSL, then:
```bash
buildozer android debug
```
The APK appears under `bin/`.

## GitHub Actions
Push to `main` or `feature/kivy-port`, or run the workflow manually. The debug APK is uploaded as a workflow artifact.

## Notes
The game rules, save structure, skins, achievements, coins, themes, level generation, stamina, lives, and scoring are based on the supplied Turtle source. The renderer is intentionally rewritten for Android.
