[Setup]
#ifndef SourceDir
#define SourceDir "dist\Stype"
#endif
#ifndef OutputName
#define OutputName "Stype_Setup"
#endif
#ifndef UserDataDir
#define UserDataDir "{userappdata}\Stype"
#endif
#ifndef StartupValueName
#define StartupValueName "Stype"
#endif

AppName=Stype
AppVersion=2.1.2
AppPublisher=Stype
AppPublisherURL=https://stype.live
DefaultDirName={autopf}\Stype
DefaultGroupName=Stype
UninstallDisplayIcon={app}\Stype.exe
PrivilegesRequired=lowest

; Output — single self-contained installer EXE, no disk spanning
OutputDir=installer_output
OutputBaseFilename={#OutputName}
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
CloseApplications=yes
RestartApplications=no

[Files]
; Bundle the entire PyInstaller output folder into the single installer EXE
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
; Start Menu shortcut
Name: "{group}\Stype"; Filename: "{app}\Stype.exe"
; Desktop shortcut
Name: "{userdesktop}\Stype"; Filename: "{app}\Stype.exe"; IconFilename: "{app}\Stype.exe"

[Registry]
; Stype can add this per-user value from its Settings screen. Do not create or
; change it during installation, but always remove it during uninstall.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "{#StartupValueName}"; Flags: dontcreatekey uninsdeletevalue

[UninstallDelete]
; The downloaded speech models are the largest part of Stype's disk usage.
; Remove the complete app-owned profile, including models, settings, history,
; and logs, after the installed program has been removed.
Type: filesandordirs; Name: "{#UserDataDir}"

[Run]
; Optional: launch after install
Filename: "{app}\Stype.exe"; Description: "Launch Stype"; Flags: nowait postinstall skipifsilent
