; Inno Setup script for Business ERP System.
;
; Installs the single-file exe produced by the committed PyInstaller spec
; (reproducible build -- see BusinessERPSystem.spec for the full config):
;
;   pip install -r requirements-build.txt
;   pyinstaller BusinessERPSystem.spec
;
; That spec is the CLI-equivalent of the original ad-hoc command
; (--onefile --windowed --name "Business ERP System", the same --add-data/
; --hidden-import flags), plus UPX disabled and a Windows version resource
; (version_info.txt) -- it still produces dist\Business ERP System.exe, so
; nothing below needed to change to stay compatible with it.
;
; Default install location is the user's own LocalAppData folder, not
; "C:\Program Files" — the app writes its database and permanent Excel/Word
; files into a "data" folder right next to the exe, and Program Files is
; write-protected for standard (non-admin) users. Installing per-user avoids
; needing admin rights and avoids UAC virtualization surprises entirely.
;
; Build with Inno Setup (download: https://jrsoftware.org/isdl.php):
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
; Output installer lands in Output\BusinessERPSystemSetup.exe

#define MyAppName "Business ERP System"
#define MyAppVersion "1.0.1"
#define MyAppExeName "Business ERP System.exe"

[Setup]
AppId={{8F1B7E2A-4C3D-4E5F-9A6B-1D2E3F4A5B6C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=BusinessERPSystemSetup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
; No "data" folder is bundled here on purpose -- see [Files] below. The app
; creates it itself on first run, next to wherever the exe ends up installed.

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
; Only the exe itself. Never bundle an existing "data" folder from the build
; machine into the installer -- that would ship real database/document
; content to every installation. Each install starts with its own fresh,
; empty "data" folder, created automatically the first time the app runs.
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName} now"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Prompt-free uninstall removes only the exe itself; the "data" folder (real
; database + permanent Excel/Word documents) is deliberately left behind so
; uninstalling the app can never destroy business data. Delete it manually
; from the install folder if you really want to wipe everything.
