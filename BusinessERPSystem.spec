# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for Business ERP System (desktop.py).

Committed to source control (instead of relying on an ad-hoc CLI command)
so every release build is reproducible byte-for-byte-equivalent from the
same inputs: same entry point, same bundled data, same hidden imports, same
packaging flags, every time, by anyone.

This replaces the previously-documented command:

    pyinstaller --onefile --windowed --name "Business ERP System" \
      --add-data "app/templates;app/templates" \
      --add-data "app/static;app/static" \
      --hidden-import passlib.handlers.bcrypt \
      desktop.py

Build with:

    pyinstaller BusinessERPSystem.spec

Still produces a single --onefile-equivalent exe at
dist\Business ERP System.exe, so installer.iss (which packages
dist\{#MyAppExeName}) needs no changes.

Two additions beyond the original CLI command:

- upx=False: UPX-compressed executables are one of the most common
  antivirus false-positive triggers for legitimate PyInstaller apps (UPX is
  also the most common malware packer, so AV heuristics weight it heavily
  regardless of payload). The size savings aren't worth that tradeoff here.
- version='version_info.txt': embeds CompanyName/ProductName/FileDescription/
  FileVersion/LegalCopyright into the exe's Windows version resource, so it
  no longer looks anonymous in Explorer's Properties dialog or to AV/
  SmartScreen reputation systems.

No icon is set: no .ico file currently exists in the project (only
app/static/images/hal-logo.jpeg, a JPEG, which Windows' exe icon resource
cannot use directly). Convert that logo to a .ico and pass it as
`icon='path/to/app_icon.ico'` below when one is produced -- Inno Setup will
pick up the icon automatically from the exe's own resource, no installer
changes needed.
"""

block_cipher = None

a = Analysis(
    ['desktop.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('app/templates', 'app/templates'),
        ('app/static', 'app/static'),
    ],
    hiddenimports=['passlib.handlers.bcrypt'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='Business ERP System',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='version_info.txt',
    icon=None,
)
