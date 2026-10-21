# MSB Recorder

MSB Recorder is a Windows desktop screen recorder built with Python and Flet.
It supports full-screen, selected-window, and drag-to-select area recording,
with optional audio, webcam, cursor, click, and keyboard capture. The
main-screen Include controls are quick switches synchronized with the capture
switches in Settings. Audio capture requires a microphone or Windows speaker
loopback device; available inputs are listed automatically. When both
microphone and system audio are selected, they are mixed automatically into
the recording. Use the camera button to save a PNG
screenshot in the configured recordings folder. Screenshot Settings let you
choose PNG or JPEG; JPEG screenshots use maximum quality. Screen mode captures
the full screen, Window mode captures the selected window, and Area mode
captures the selected screen region. Settings can turn saved-recording and
saved-screenshot confirmation popups off; capture errors are still reported.
In Area mode, the selected region stays visible with a green border while idle
and a red border while recording. Drag
the center move handle to reposition the region, or drag its border and corner
handles to resize it. Press Escape or click the close control on the area frame
to switch back to Screen mode; an active area recording is stopped first. The
frame is excluded from screen capture, so it remains visible on screen without
appearing in the recorded video. Area recordings preserve the selected
region's proportions and center it at the chosen output resolution, adding
black space where the aspect ratios differ instead of stretching the image.
Keyboard shortcuts for Record, Stop, Pause/Resume, and Screenshot can be
set by clicking the shortcut button and pressing the desired key or key
combination, including a single modifier key; the defaults are F9, F10, F11,
and F12. Each button shows the action name beside its assigned key. Pause
temporarily suspends captured video and audio.
Enable the Keys Include switch to show pressed keys in the recording. Special
keys use readable labels such as ENTER, SHIFT, TAB, arrow keys, and F-keys;
key combinations are shown together in a high-contrast overlay for two seconds.
The Keys Overlay settings let you place the indicator at the bottom left,
center, or right, choose a small, medium, or large size, and select a custom
overlay color. Choose All Keys to display every key press, or Special Keys to
hide letters and numbers while still displaying special keys.
Press Save Changes to keep Settings selections between app launches. They are
stored for the current Windows user in
`%LOCALAPPDATA%\MSB Recorder\settings.json` and restored after a computer restart.

## Requirements

- Windows 10 or later
- Python 3.11 or later
- Git (to clone the repository)

## Installation

Open PowerShell in the project folder and create a virtual environment:

```powershell
py -3.11 -m venv .venv
```

Activate the environment and install the project dependencies:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks activation scripts, either allow scripts for the current
PowerShell process with
`Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process`, then
activate the environment again, or run the install command directly without
activating:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run

With the virtual environment activated, start the application with:

```powershell
python main.py
```

The application uses `imageio-ffmpeg` to provide FFmpeg for video encoding; a
separate FFmpeg installation is not required.
