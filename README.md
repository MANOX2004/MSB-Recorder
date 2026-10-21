# MSB Recorder

MSB Recorder is a Windows desktop screen recorder built with Python and Flet.
It supports video recording with optional audio, webcam, cursor, click, and
keyboard capture. The main-screen Include controls are quick switches
synchronized with the capture switches in Settings. Audio capture requires a
microphone or Windows speaker loopback device; available inputs are listed
automatically.

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
