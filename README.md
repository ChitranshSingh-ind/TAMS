# TAMS — Tuition & Coaching Management System

**TAMS** is a comprehensive, local-first desktop management suite for tuition and coaching institutes. Built with Python, PyQt6, SQLAlchemy, and SQLite, TAMS features complete student tracking, attendance and test results, fees and expenses accounting, curriculum progress, analytics dashboards, and an automated WhatsApp messaging system powered by Meta Cloud API and the **CoachingHelper** companion background service.

---

## Architecture Overview

TAMS consists of two coordinated desktop components that share a single local-first SQLite database:

```
┌────────────────────────────────────────────────────────┐
│               TAMS Desktop Application                 │
│  - Interactive PyQt6 GUI (Navy, Gold & Cream palette) │
│  - Student management, attendance, tests & fees       │
│  - Message composer, templates & automation rules      │
│  - Operates completely offline or online               │
└──────────────────────────┬─────────────────────────────┘
                           │ Shared SQLite (WAL Mode, 30s busy timeout)
┌──────────────────────────▼─────────────────────────────┐
│          CoachingHelper Companion Daemon               │
│  - Standalone process (System Tray or Headless)        │
│  - Background queue polling & Meta Cloud API dispatch  │
│  - Atomic claim leasing & exponential retry backoff    │
│  - Automated daily database backups & health status    │
└────────────────────────────────────────────────────────┘
```

---

## Key Features

1. **Local-First & Multi-Process SQLite Safety**
   - **Write-Ahead Logging (WAL)**: Concurrent read and write access across processes without locks.
   - **Busy Timeout**: 30.0-second busy handler prevents `database is locked` exceptions during simultaneous activity.
   - **Atomic Claim Leasing**: Atomic SQL updates ensure multiple workers or app instances never send duplicate WhatsApp messages.
   - **Expired Lease Recovery**: Automatically recovers orphaned messages if a background process halts unexpectedly.

2. **Official Meta Cloud API WhatsApp Integration**
   - Full support for WhatsApp Cloud API v17.0–v21.0.
   - Dynamic parameter extraction and validation against registered Meta template structures.
   - Pre-flight parameter count validation (`PARAM_MISMATCH` flag) to prevent unnecessary failed API calls.
   - Ambiguous network timeout detection (`[AMBIGUOUS_OUTCOME]`) to protect against duplicate parent billing notifications.

3. **CoachingHelper Companion Service**
   - Runs silently in the Windows system tray or as a headless background daemon.
   - Dedicated non-blocking worker threads keep tray menus responsive under network load.
   - Built-in Inter-Process Communication (IPC) for commands: Start, Stop, Pause, Resume, and "Process Queue Now".
   - Bounded rotating file logging (5MB, 3 backups) with automatic redaction of Meta tokens and authorization headers.
   - Windows Registry autostart integration (`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`).

---

## Installation & Setup

### Option 1: Windows Installer (Recommended for End Users)

1. Download `TAMS_Setup_v2.0.0.exe` from Releases.
2. Run the installer. You may select:
   - **Create a desktop shortcut**
   - **Launch CoachingHelper companion automatically at Windows startup**
3. Finish the wizard. TAMS is ready to use!

### Option 2: Running from Source (Developers)

Ensure Python 3.10+ is installed on your machine.

```bash
# Clone the repository
git clone https://github.com/ChitranshSingh-ind/TAMS.git
cd TAMS

# Create and activate virtual environment
python -m venv .venv

# On Linux / macOS:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate.bat

# Install dependencies
pip install -r requirements.txt

# Apply database migrations
alembic upgrade head

# Launch TAMS main application
python main.py

# (Optional) Launch CoachingHelper companion
python coaching_helper_main.py
```

---

## Configuring WhatsApp Cloud API

1. Navigate to **TAMS → Settings (gear icon) → WhatsApp**.
2. Select your environment (**Test / Sandbox** or **Production**).
3. Enter your Meta credentials:
   - **Phone Number ID**: Available in Meta Developer Portal → WhatsApp → API Setup.
   - **WABA ID**: WhatsApp Business Account ID.
   - **Graph API Version**: Defaults to `v21.0`.
   - **Permanent Access Token**: Securely saved to local encrypted credential storage.
4. Click **Test API Connection** to verify credentials.
5. Send a test message to ensure template delivery.

---

## Automated Backups & Maintenance

- CoachingHelper automatically verifies and takes a safety snapshot of `tams.db` every 24 hours.
- Backups are stored in:
  - **Windows**: `%APPDATA%\TAMS\backups\`
  - **Linux**: `~/.local/share/TAMS/backups/`
- You can create manual backups, verify database integrity, or restore previous backups directly in **Settings → Backup & Maintenance**.

---

## Building the Windows Executable & Installer

To build standalone `.exe` binaries and the Inno Setup installer on a Windows development system:

1. Double-click `build_windows.bat` or run in Command Prompt:
   ```cmd
   build_windows.bat
   ```
2. The script will:
   - Upgrade virtual environment packages from `requirements.txt`.
   - Execute `alembic upgrade head` to ensure schemas match.
   - Run PyInstaller with `tams.spec` to output `dist\TAMS\` containing both `TAMS.exe` and `CoachingHelper.exe`.
   - Compile `installer.iss` using Inno Setup 6 into `Output\TAMS_Setup_v2.0.0.exe`.

---

## Troubleshooting & Diagnostics

- **WhatsApp messages show "Sending" for a long time**:
  Check if CoachingHelper is active in the tray. If stopped, click **⚡ Process Queue Now** in **Settings → Backup & Maintenance** or launch `CoachingHelper.exe`.
- **Logs & Diagnostic Information**:
  Companion diagnostic logs are written with automatic credential masking to:
  - **Windows**: `%APPDATA%\TAMS\logs\coaching_helper.log`
  - **Linux**: `~/.local/share/TAMS/logs/coaching_helper.log`
- **Parameter Mismatch Errors (`PARAM_MISMATCH`)**:
  Occurs when an automation rule sends fewer parameters than the Meta template expects. Edit the template in **Messages → Templates** to adjust parameter placeholders.
