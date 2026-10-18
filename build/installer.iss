; FileDrop installer (Inno Setup 6). Built by build/build.ps1, which passes the version:
;   ISCC.exe /DMyAppVersion=0.1.0 build\installer.iss
; Output: build\out\FileDrop-Setup-<version>.exe
;
; Installs to Program Files, adds a Start menu entry, optional desktop icon and
; "start when I sign in", and a Windows Firewall rule so phones can connect
; without the firewall prompt. Uninstalling keeps users' files and the database.

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#define MyAppName "FileDrop"
#define MyAppExe "FileDrop.exe"

[Setup]
AppId={{7B6C2A0E-3F4D-4E8B-9C11-2D5A6F0B9E31}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=FileDrop
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir=out
OutputBaseFilename=FileDrop-Setup-{#MyAppVersion}
SetupIconFile=filedrop.ico
UninstallDisplayIcon={app}\{#MyAppExe}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Licence agreement page (the user must accept it to install).
LicenseFile=..\console\EULA.txt
; Close a running FileDrop before installing or uninstalling.
AppMutex=Local\FileDrop.SingleInstance
CloseApplications=yes
; Code signing: once you have a certificate, configure a SignTool named "signtool" in
; the Inno Setup IDE (Tools > Configure Sign Tools) and uncomment:
; SignTool=signtool
; SignedUninstaller=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; Flags: unchecked
Name: "autostart"; Description: "Start FileDrop when I sign in to Windows (runs in the tray)"

[Files]
Source: "out\FileDrop\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\console\THIRD-PARTY-NOTICES.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\console\EULA.txt"; DestDir: "{app}"; DestName: "LICENCE AGREEMENT.txt"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "FileDrop"; \
    ValueData: """{app}\{#MyAppExe}"" --background"; Tasks: autostart; Flags: uninsdeletevalue

[Run]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""FileDrop"""; \
    Flags: runhidden; StatusMsg: "Configuring Windows Firewall..."
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""FileDrop"" dir=in action=allow program=""{app}\{#MyAppExe}"" enable=yes profile=private,public"; \
    Flags: runhidden
Filename: "{app}\{#MyAppExe}"; Description: "Start FileDrop now"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/IM {#MyAppExe} /F"; Flags: runhidden; RunOnceId: "StopFileDrop"
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""FileDrop"""; Flags: runhidden; RunOnceId: "RemoveFirewallRule"
