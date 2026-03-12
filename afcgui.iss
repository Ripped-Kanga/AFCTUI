; Inno Setup script — AFCTUI Windows GUI installer
;
; Local build:
;   iscc afcgui.iss
;
; CI build (version injected from git tag):
;   iscc /DAppVersion=1.2.3 afcgui.iss
;
; Requires dist\afcgui.exe to already exist (built by PyInstaller).

#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

#define AppName      "AFCTUI"
#define AppPublisher "Ripped-Kanga"
#define AppURL       "https://github.com/Ripped-Kanga/AFCTUI"
#define AppExeName   "afcgui.exe"

[Setup]
AppId={{7F3D2A8B-4E91-4C52-B6F0-8D2E1A9C3F7E}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
LicenseFile=LICENSE
SetupIconFile=src\afctui\assets\afctui.ico
UninstallDisplayIcon={app}\afcgui.exe
OutputDir=dist
OutputBaseFilename=afcgui-setup-{#AppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; \
  GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}";                          Filename: "{app}\{#AppExeName}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}";    Filename: "{uninstallexe}"
Name: "{commondesktop}\{#AppName}";                  Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; \
  Description: "{cm:LaunchProgram,{#AppName}}"; \
  Flags: nowait postinstall skipifsilent
