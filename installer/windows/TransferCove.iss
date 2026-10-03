; TransferCove Windows installer for Inno Setup 6+
; Build the Flet application first:
;   poetry run flet build windows --yes --build-version (poetry version --short)
; Then compile this file with Inno Setup Compiler.

#define MyAppName "TransferCove"
#define MyAppExeName "TransferCove.exe"
#define BuildDir "..\..\build\windows"
#ifndef MyAppVersion
  #define MyAppVersion GetStringFileInfo(BuildDir + "\" + MyAppExeName, "ProductVersion")
#endif
#if MyAppVersion == ""
  #error "Build the application first or pass /DMyAppVersion to ISCC"
#endif
#define MyAppPublisher "AlexZha-dev"
#define MyAppURL "https://github.com/AlexZha-dev/transfercove"
#ifndef InstallerName
  #define InstallerName "TransferCove-Setup-" + MyAppVersion
#endif

[Setup]
AppId={{A6F4C3F3-2DA6-4AF4-9E2F-7C0A0200BEEF}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=commandline
OutputDir=..\..\dist\installer
OutputBaseFilename={#InstallerName}
SetupIconFile=..\..\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
LicenseFile=..\..\LICENSE
InfoBeforeFile=SECURITY-NOTICE.txt
InfoAfterFile=..\..\THIRD-PARTY-NOTICES.txt
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#BuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\THIRD-PARTY-NOTICES.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "SECURITY-NOTICE.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
