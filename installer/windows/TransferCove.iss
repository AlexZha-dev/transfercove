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
#define TransferCoveId "{A6F4C3F3-2DA6-4AF4-9E2F-7C0A0200BEEF}"
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
AppId={#StringChange(TransferCoveId, '{', '{{')}
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

[Code]
const
  UninstallKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#TransferCoveId}_is1';

var
  UpgradingInPlace: Boolean;

function NewerRelease(Version: Int64): Boolean;
begin
  { Ignore Flutter's CI build number when repairing the same release. }
  Result := ComparePackedVersion(Version and (not Int64($FFFF)),
    PackVersionComponents({#Major}, {#Minor}, {#Patch}, 0)) > 0;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  DisplayVersion, InstallLocation: String;
  InstalledVersion: Int64;
begin
  Result := '';
  UpgradingInPlace := RegQueryStringValue(HKA, UninstallKey, 'InstallLocation', InstallLocation) and
    (CompareText(AddBackslash(InstallLocation), AddBackslash(ExpandConstant('{app}'))) = 0);
  if RegQueryStringValue(HKA, UninstallKey, 'DisplayVersion', DisplayVersion) then
  begin
    if not StrToVersion(DisplayVersion, InstalledVersion) then
      Result := 'Cannot read the installed TransferCove version: ' + DisplayVersion
    else if NewerRelease(InstalledVersion) then
      Result := 'A newer version of TransferCove (' + DisplayVersion +
        ') is already installed. Setup cannot install version {#MyAppVersion} over it.';
  end;
  if (Result = '') and GetPackedVersion(ExpandConstant('{app}\{#MyAppExeName}'), InstalledVersion) then
    if NewerRelease(InstalledVersion) then
      Result := 'The selected directory contains a newer TransferCove executable (' +
        VersionToStr(InstalledVersion) + ').';
end;

function GetFileAttributesW(Path: String): LongWord;
  external 'GetFileAttributesW@kernel32.dll stdcall';

procedure RemoveRetiredPath(RelativePath: String; IsDirectory: Boolean);
var
  Root, Path, Parent: String;
  Attributes: LongWord;
begin
  Root := ExpandConstant('{app}');
  Path := AddBackslash(Root) + RelativePath;
  Parent := Path;
  repeat
    Attributes := GetFileAttributesW(Parent);
    if Attributes = $FFFFFFFF then Exit;
    if (Attributes and $400) <> 0 then begin
      Log('Skipping reparse point during upgrade cleanup: ' + Parent);
      Exit;
    end;
    if CompareText(Parent, Root) = 0 then Break;
    Parent := ExtractFileDir(Parent);
  until False;
  if IsDirectory then
    RemoveDir(Path)  { Only removes empty directories. }
  else if FileExists(Path) and not DeleteFile(Path) then
    RaiseException('Could not remove the retired TransferCove file: ' + Path);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep <> ssPostInstall) or not UpgradingInPlace then Exit;
  { Compile only paths that this release has retired. }
#define Inventory FileOpen(AddBackslash(SourcePath) + "released-payload.txt")
#if !Inventory
  #error "Cannot read the released Windows payload inventory"
#endif
#sub EmitCleanup
  #define Entry FileRead(Inventory)
  #if Copy(Entry, Len(Entry), 1) == "\"
    #define Folder Copy(Entry, 1, Len(Entry) - 1)
    #if !DirExists(BuildDir + "\" + Folder)
  RemoveRetiredPath('{#Folder}', True);
    #endif
  #elif !FileExists(BuildDir + "\" + Entry)
  RemoveRetiredPath('{#Entry}', False);
  #endif
#endsub
#for {0; !FileEof(Inventory); 0} EmitCleanup
#expr FileClose(Inventory)
end;
