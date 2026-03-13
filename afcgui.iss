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

#define AppName      "AFCGUI"
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

[Code]
{ Check whether the Microsoft Visual C++ 2015-2022 x64 Redistributable is
  installed.  Qt (PySide6) and the PyInstaller-bundled exe both require it.
  All VS 2015-2022 releases share the same runtime and registry key. }
function VCRedistInstalled: Boolean;
var
  Installed: Cardinal;
begin
  Result := RegQueryDWordValue(
    HKEY_LOCAL_MACHINE,
    'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\X64',
    'Installed',
    Installed
  ) and (Installed = 1);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if not VCRedistInstalled then
    begin
      MsgBox(
        'AFCGUI requires the Microsoft Visual C++ 2015-2022 Redistributable (x64).' + #13#10 + #13#10 +
        'If the application fails to start with a DLL error, download and' + #13#10 +
        'install it from Microsoft, then restart AFCGUI:' + #13#10 + #13#10 +
        'https://aka.ms/vs/17/release/vc_redist.x64.exe',
        mbInformation,
        MB_OK
      );
    end;
  end;
end;
