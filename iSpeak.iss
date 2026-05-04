[Setup]
AppName=iSpeak
AppVersion=1.0
DefaultDirName={pf}\iSpeak
DefaultGroupName=iSpeak
UninstallDisplayIcon={app}\ispeak.exe
Compression=lzma2
SolidCompression=yes
OutputDir=userdocs:Inno Setup Examples Output
; This points to your icon file for the installer itself
SetupIconFile="C:\Users\sumit\OneDrive\Desktop\Random\iSpeak\icon.ico"

[Files]
; This grabs everything from your dist folder
Source: "C:\Users\sumit\OneDrive\Desktop\Random\iSpeak\dist\ispeak\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
; This creates the shortcut on your Start Menu
Name: "{group}\iSpeak"; Filename: "{app}\ispeak.exe"
; This creates the shortcut on your Desktop with your icon
Name: "{commondesktop}\iSpeak"; Filename: "{app}\ispeak.exe"; IconFilename: "{app}\ispeak.exe"

[Run]
; This gives the user the option to launch the app immediately after installing
Filename: "{app}\ispeak.exe"; Description: "Launch iSpeak"; Flags: nowait postinstall skipifsilent