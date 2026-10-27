# MSB Recorder

A free, lightweight screen recorder for Windows, built with Python and [Flet](https://flet.dev).

Record your full screen, a single window, or a custom area, with optional system audio, microphone, webcam, cursor, mouse clicks, and on-screen key presses.

**Version:** 1.0 · **Platform:** Windows 10 or later

---

## Features

### Capture modes

| Mode | Description |
| --- | --- |
| **Screen** | Records the full screen. If more than one display is connected, you can choose which one. |
| **Window** | Records a specific open window that you pick from a list. |
| **Area** | Drag to select any region of the screen and record only that part. |

### Include options

The **Include** switches on the main screen are quick toggles that stay in sync with the capture switches in Settings.

- **System audio**: records what your PC is playing (Windows speaker loopback)
- **Mic**: records from your microphone
- **Webcam**: adds a webcam inset to the video
- **Cursor**: shows the mouse cursor
- **Clicks**: highlights mouse clicks
- **Keys**: shows pressed keys on screen

When both Mic and System audio are enabled, they are mixed into a single audio track automatically. Available audio and camera devices are detected and listed for you.

### Area mode

- The selected region stays visible with a **green border** when idle and a **red border** while recording.
- Drag the **center handle** to move the region, or drag the **borders and corners** to resize it.
- Press **Esc** or click the close control on the frame to return to Screen mode. If an area recording is running, it is stopped first.
- The frame is excluded from capture, so it never appears in your video.
- The region keeps its proportions: it is centered in the output resolution with black bars added where the aspect ratios differ, so nothing gets stretched.

### Key press overlay

When **Keys** is enabled, pressed keys are drawn on the video in a high-contrast overlay for two seconds. Special keys use readable labels such as `ENTER`, `SHIFT`, `TAB`, arrow keys, and F-keys, and combinations are shown together.

Overlay settings:

- **Position:** left, center, or right (bottom of the video)
- **Size:** small, medium, or large
- **Color:** any custom color
- **Key type:** *All Keys* shows every key press; *Special Keys* hides letters and numbers

### Webcam overlay

Choose which camera to use and place the inset in any of the four corners (top left, top right, bottom left, bottom right), with a small gap from the edges.

### Screenshots

Click the camera button to save a screenshot of the current capture target (screen, window, or area) to your recordings folder. Choose **PNG** or **JPEG** in Settings; JPEG screenshots are saved at maximum quality.

### Keyboard shortcuts

Global shortcuts work even when the app is not in focus.

| Action | Default |
| --- | --- |
| Record | `F9` |
| Stop | `F10` |
| Pause / Resume | `F11` |
| Screenshot | `F12` |

To change a shortcut, open Settings, click the shortcut button, and press the key or key combination you want. A single modifier key is allowed. Each button shows the action name beside its assigned key. Duplicate shortcuts are not accepted. Pause suspends both video and audio capture.

### Output settings

| Setting | Options |
| --- | --- |
| Resolution | 1280 x 720 (HD), 1920 x 1080 (Full HD), 3840 x 2160 (4K) |
| Frame rate | 30 FPS, 60 FPS |
| Quality | Medium, High, Ultra Lossless |
| Format | MP4 (recommended), MKV, AVI |
| Save folder | Any folder you choose |

Defaults are 1920 x 1080, 60 FPS, High quality, MP4.

Recordings and screenshots are saved to `C:\Users\<you>\Videos\MSB Recordings` unless you change the save folder. Saved-recording and saved-screenshot confirmation popups can be turned off in Settings; capture errors are always reported.

### Saved settings

Click **Save Changes** in Settings to keep your choices between launches. They are stored per Windows user at:

```
%LOCALAPPDATA%\MSB Recorder\settings.json
```

### Update check

On startup, the app checks the latest GitHub release and shows a notification with release notes if a newer version is available. This check needs an internet connection and is skipped silently if it fails.

---

## Requirements

- Windows 10 or later
- Python 3.11 or later
- Git (to clone the repository)

FFmpeg is provided by the `imageio-ffmpeg` package, so you do **not** need to install it separately.

## Installation

Clone the repository and open PowerShell in the project folder:

```powershell
git clone https://github.com/MANOX2004/MSB-Recorder.git
cd MSB-Recorder
```

Create a virtual environment:

```powershell
py -3.11 -m venv .venv
```

Activate it and install the dependencies:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks the activation script, either allow scripts for the current session and activate again:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
```

or skip activation and call the environment's Python directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run

With the virtual environment activated:

```powershell
python main.py
```

Or without activating it:

```powershell
.\.venv\Scripts\python.exe main.py
```

## Quick start

1. Choose what to record: **Screen**, **Window**, or **Area**.
2. Turn on the **Include** options you need (audio, webcam, cursor, clicks, keys).
3. Press the record button or `F9`.
4. Press stop or `F10` when you are done. Use `F11` to pause and resume.
5. Click **Open recordings** to find your file.

## Project structure

```
MSB-Recorder/
├── main.py             # App entry point and main window, dialogs, hotkeys
├── logic.py            # Capture, audio, webcam, overlays, FFmpeg encoding
├── ui_components.py    # Reusable UI pieces (title bar, mode picker, controls)
├── settings_store.py   # Loading and saving settings.json
├── requirements.txt    # Python dependencies
└── assets/             # App icon and images
```

## Dependencies

| Package | Used for |
| --- | --- |
| `flet` | Desktop user interface |
| `mss` | Fast screen capture |
| `opencv-python`, `numpy`, `pillow` | Frame processing, overlays, screenshots |
| `imageio-ffmpeg` | Bundled FFmpeg for encoding and muxing |
| `SoundCard` | Microphone and system audio capture |
| `pynput` | Global hotkeys and key press capture |
| `pywin32`, `pyautogui`, `PyGetWindow`, `PyScreeze` | Windows and cursor handling |
| `screeninfo` | Detecting connected displays |
| `requests` | Checking for new releases |

## Troubleshooting

- **No system audio option:** your PC may not expose a speaker loopback device. Check that an output device is enabled in Windows Sound settings.
- **No microphone or webcam listed:** connect the device, then reopen Settings so the list refreshes.
- **"Select an area before starting the recording":** switch to Area mode and drag a region first.
- **Settings reset after an error:** if `settings.json` is corrupted, delete it from `%LOCALAPPDATA%\MSB Recorder\` and start the app again.

## About

Developed by **Manoj Senevirathna**. Made in Sri Lanka ❤️
