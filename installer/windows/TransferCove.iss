; TransferCove Windows installer for Inno Setup 6.3+
; Build the Flet application first:
;   poetry run flet build windows --yes --build-version (poetry version --short)
; Then compile this file with Inno Setup Compiler.

#define MyAppName "TransferCove"
#define MyAppExeName "TransferCove.exe"
#define BuildDir "..\..\build\windows"
#if Ver < EncodeVer(6, 3, 0)
  #error "Inno Setup 6.3 or newer is required"
#endif
#ifdef MyAppId
  #error "TransferCove uses a fixed AppId for update discovery"
#endif
#define AppBinary AddBackslash(SourcePath) + BuildDir + "\" + MyAppExeName
#define Major
#define Minor
#define Patch
#define BuildNumber
#if !FileExists(AppBinary) || GetVersionComponents(AppBinary, Major, Minor, Patch, BuildNumber) == ""
  #error "Build TransferCove.exe with Windows version information before compiling Setup"
#endif
; Flutter stores the CI build number in the fourth numeric component.
#define BinaryRelease Str(Major) + "." + Str(Minor) + "." + Str(Patch)
#ifndef MyAppVersion
  #define MyAppVersion BinaryRelease
#elif MyAppVersion != BinaryRelease
  #error "Project version differs from the built TransferCove.exe; rebuild the application"
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
VersionInfoVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
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
