[Setup]
AppName=Stype
AppVersion=2.0
DefaultDirName={pf}\Stype
DefaultGroupName=Stype
UninstallDisplayIcon={app}\Stype.exe
Compression=lzma2
SolidCompression=yes
OutputDir=dist
; This points to your icon file for the installer itself
SetupIconFile="assets\icon.ico"

[Files]
; This grabs everything from your dist folder
Source: "dist\Stype\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
; This creates the shortcut on your Start Menu
Name: "{group}\Stype"; Filename: "{app}\Stype.exe"
; This creates the shortcut on your Desktop with your icon
Name: "{commondesktop}\Stype"; Filename: "{app}\Stype.exe"; IconFilename: "{app}\Stype.exe"

[Run]
; This gives the user the option to launch the app immediately after installing
Filename: "{app}\Stype.exe"; Description: "Launch Stype"; Flags: nowait postinstall skipifsilent