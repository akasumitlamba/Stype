[Setup]
AppName=Stype
AppVersion=2.0
AppPublisher=Stype
AppPublisherURL=https://stype.live
DefaultDirName={autopf}\Stype
DefaultGroupName=Stype
UninstallDisplayIcon={app}\Stype.exe

; Output — single self-contained installer EXE, no disk spanning
OutputDir=installer_output
OutputBaseFilename=Stype_Setup
; DiskSpanning removed: it splits the installer into multiple .bin part files
; which other users don't have, causing "file not found" errors on install.

; Compression — lzma2/ultra64 gives best compression for a single-file setup
Compression=lzma2/ultra64
SolidCompression=yes

; Appearance
SetupIconFile="assets\icon.ico"
WizardStyle=modern

; Require Windows 10 or later (needed for PyQt6 + faster-whisper)
MinVersion=10.0

[Files]
; Bundle the entire PyInstaller output folder into the single installer EXE
Source: "dist\Stype\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
; Start Menu shortcut
Name: "{group}\Stype"; Filename: "{app}\Stype.exe"
; Desktop shortcut
Name: "{commondesktop}\Stype"; Filename: "{app}\Stype.exe"; IconFilename: "{app}\Stype.exe"

[Run]
; Optional: launch after install
Filename: "{app}\Stype.exe"; Description: "Launch Stype"; Flags: nowait postinstall skipifsilent