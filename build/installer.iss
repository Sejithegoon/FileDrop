; WiFiDrop installer (Inno Setup 6). Built by build/build.ps1, which passes the version:
;   ISCC.exe /DMyAppVersion=0.1.0 build\installer.iss
; Output: build\out\WiFiDrop-Setup-<version>.exe
;
; Installs to Program Files, adds a Start menu entry, optional desktop icon and
; "start when I sign in", and a Windows Firewall rule so phones can connect
; without the firewall prompt. Uninstalling keeps users' files and the database.

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#define MyAppName "WiFiDrop"
#define MyAppExe "WiFiDrop.exe"

[Setup]
AppId={{7B6C2A0E-3F4D-4E8B-9C11-2D5A6F0B9E31}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=WiFiDrop
DefaultDirName={autopf}\{#MyAppName}
; The folder page is shown on first install, and on upgrades only when the old folder can't be
; used (its drive is unplugged, or it's a USB stick). See [Code] below.
DisableDirPage=no
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir=out
OutputBaseFilename=WiFiDrop-Setup-{#MyAppVersion}
SetupIconFile=wifidrop.ico
UninstallDisplayIcon={app}\{#MyAppExe}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Licence agreement page (the user must accept it to install).
LicenseFile=..\console\EULA.txt
; Close a running WiFiDrop before installing or uninstalling.
AppMutex=Local\WiFiDrop.SingleInstance,Local\FileDrop.SingleInstance
CloseApplications=yes
; Code signing: once you have a certificate, configure a SignTool named "signtool" in
; the Inno Setup IDE (Tools > Configure Sign Tools) and uncomment:
; SignTool=signtool
; SignedUninstaller=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; Flags: unchecked
Name: "autostart"; Description: "Start WiFiDrop when I sign in to Windows (runs in the tray)"

[InstallDelete]
; Upgrading from the FileDrop beta: remove the old program file (data and settings are kept).
Type: files; Name: "{app}\FileDrop.exe"

[Files]
Source: "out\WiFiDrop\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\console\THIRD-PARTY-NOTICES.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\console\EULA.txt"; DestDir: "{app}"; DestName: "LICENCE AGREEMENT.txt"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Registry]
; Remove the FileDrop beta's start-up entry.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "FileDrop"; Flags: deletevalue dontcreatekey
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "WiFiDrop"; \
    ValueData: """{app}\{#MyAppExe}"" --background"; Tasks: autostart; Flags: uninsdeletevalue

[Run]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""FileDrop"""; Flags: runhidden
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""WiFiDrop"""; \
    Flags: runhidden; StatusMsg: "Configuring Windows Firewall..."
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""WiFiDrop"" dir=in action=allow program=""{app}\{#MyAppExe}"" enable=yes profile=private,public"; \
    Flags: runhidden
Filename: "{app}\{#MyAppExe}"; Description: "Start WiFiDrop now"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/IM {#MyAppExe} /F"; Flags: runhidden; RunOnceId: "StopWiFiDrop"
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""WiFiDrop"""; Flags: runhidden; RunOnceId: "RemoveFirewallRule"

[Code]
// The app must live on a drive that's always there. A USB stick (or an unplugged drive) would stop
// WiFiDrop and its updates whenever it's removed. Files can still be stored on such a drive.
const
  DRIVE_REMOVABLE = 2;

function GetDriveType(lpRootPathName: String): Cardinal;
  external 'GetDriveTypeW@kernel32.dll stdcall';

function DriveRoot(Path: String): String;
begin
  Result := ExtractFileDrive(Path);
  if Result <> '' then
    Result := AddBackslash(Result);
end;

function FolderUsable(Path: String): Boolean;
var
  Root: String;
begin
  Root := DriveRoot(Path);
  Result := (Root <> '') and DirExists(Root) and (GetDriveType(Root) <> DRIVE_REMOVABLE);
end;

procedure UseDefaultIfUnusable();
begin
  if not FolderUsable(WizardForm.DirEdit.Text) then
    WizardForm.DirEdit.Text := ExpandConstant('{autopf}\{#MyAppName}');
end;

procedure InitializeWizard();
begin
  UseDefaultIfUnusable();
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  if PageID = wpSelectDir then
  begin
    // Upgrading where the old folder still works: keep it, no questions.
    Result := (WizardForm.PrevAppDir <> '') and FolderUsable(WizardForm.PrevAppDir);
    if not Result then
      UseDefaultIfUnusable();
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Root: String;
begin
  Result := True;
  if CurPageID = wpSelectDir then
  begin
    Root := DriveRoot(WizardDirValue());
    if (Root = '') or not DirExists(Root) then
    begin
      MsgBox('That drive isn''t available. Choose a folder on a drive that''s connected, such as C:.', mbError, MB_OK);
      Result := False;
    end
    else if GetDriveType(Root) = DRIVE_REMOVABLE then
    begin
      MsgBox('Install WiFiDrop on a drive that''s always connected, such as C:.' + #13#10#13#10 +
        'A USB stick can be unplugged, and WiFiDrop would stop working. You can still keep your shared files on a USB or external drive: choose that inside WiFiDrop after installing.',
        mbInformation, MB_OK);
      Result := False;
    end;
  end;
end;
