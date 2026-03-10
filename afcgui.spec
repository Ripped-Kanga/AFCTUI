# PyInstaller spec file — AFCTUI Windows GUI (afcgui.exe)
#
# Build with:
#   pip install pyinstaller
#   pyinstaller afcgui.spec
#
# The resulting executable lands in dist/afcgui.exe.
#
# ─── ffmpeg licensing note ────────────────────────────────────────────────────
# ffmpeg is NOT bundled here.  Most pre-built Windows ffmpeg binaries are
# GPL-licensed (include libx264 etc.), which conflicts with AFCTUI's MIT
# licence.  Distributing a GPL binary alongside an MIT app would require the
# entire distribution to be released under the GPL.
#
# Instead, afcgui detects a missing ffmpeg at startup and offers a one-click
# "Install via winget" path (winget install --id Gyan.FFmpeg).
#
# If you build your own LGPL-only shared (DLL) ffmpeg and wish to bundle it,
# add entries like the following to `binaries` below and ensure you host the
# corresponding ffmpeg source code per LGPL §4:
#
#   binaries=[
#       (r'C:\ffmpeg-lgpl\bin\ffmpeg.exe',  '.'),
#       (r'C:\ffmpeg-lgpl\bin\ffprobe.exe', '.'),
#       (r'C:\ffmpeg-lgpl\bin\ffplay.exe',  '.'),
#       (r'C:\ffmpeg-lgpl\bin\*.dll',       '.'),
#   ],
# ──────────────────────────────────────────────────────────────────────────────

block_cipher = None

a = Analysis(
    ['src/afctui/gui_main.py'],
    pathex=['src'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'afctui.converter',
        'afctui.player',
        'afctui.gui_scrubber',
        'afctui.gui_app',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['rthook_log.py'],
    excludes=[
        # TUI-only dependencies — not needed in the GUI build
        'textual',
        'rich',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='afcgui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,      # No console window — pure GUI app
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,          # Set to an .ico path here to add a custom app icon
)
