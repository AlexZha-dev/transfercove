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
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent; Check: CleanupSucceeded

[Code]
const
  UninstallKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#TransferCoveId}_is1';

var
  UpgradingInPlace: Boolean;
  CleanupErrors: String;

function NewerRelease(Version: Int64): Boolean;
begin
  { Ignore Flutter's CI build number when repairing the same release. }
  Result := ComparePackedVersion(Version and (not Int64($FFFF)),
    PackVersionComponents({#Major}, {#Minor}, {#Patch}, 0)) > 0;
end;

function ReadDigits(Value: String; var Cursor: Integer): String;
var
  Start: Integer;
begin
  Start := Cursor;
  while Cursor <= Length(Value) do begin
    if (Value[Cursor] < '0') or (Value[Cursor] > '9') then Break;
    Inc(Cursor);
  end;
  Result := Copy(Value, Start, Cursor - Start);
end;

function ParseDisplayRelease(Value: String; var Version: Int64): Boolean;
var
  Cursor, Index, Part: Integer;
  Release: String;
begin
  Result := False;
  Cursor := 1;
  for Index := 1 to 3 do begin
    if Index > 1 then begin
      if Copy(Value, Cursor, 1) <> '.' then Exit;
      Inc(Cursor);
    end;
    Part := StrToIntDef(ReadDigits(Value, Cursor), -1);
    if (Part < 0) or (Part > 65535) then Exit;
  end;
  Release := Copy(Value, 1, Cursor - 1);
  if Cursor <= Length(Value) then begin
    if (Value[Cursor] <> '.') and (Value[Cursor] <> '+') then Exit;
    Inc(Cursor);
    if ReadDigits(Value, Cursor) = '' then Exit;
  end;
  Result := (Cursor > Length(Value)) and StrToVersion(Release, Version);
end;

function CheckInstalledVersion: String;
var
  DisplayVersion, InstallLocation: String;
  RegisteredVersion, ExeVersion: Int64;
  HasExeVersion: Boolean;
begin
  Result := '';
  UpgradingInPlace := RegQueryStringValue(HKA, UninstallKey, 'InstallLocation', InstallLocation) and
    (CompareText(AddBackslash(InstallLocation), AddBackslash(ExpandConstant('{app}'))) = 0);
  HasExeVersion := GetPackedVersion(ExpandConstant('{app}\{#MyAppExeName}'), ExeVersion);
  if RegKeyExists(HKA, UninstallKey) then
  begin
    if RegQueryStringValue(HKA, UninstallKey, 'DisplayVersion', DisplayVersion) and
        ParseDisplayRelease(DisplayVersion, RegisteredVersion) then begin
      if NewerRelease(RegisteredVersion) then
        Result := 'A newer version of TransferCove (' + DisplayVersion +
          ') is already installed. Setup cannot install version {#MyAppVersion} over it.';
    end else if not (UpgradingInPlace and HasExeVersion) then
      Result := 'Cannot determine the release of the registered TransferCove installation.'
    else
      Log('Using the registered installation executable to determine its release.');
  end;
  if (Result = '') and HasExeVersion then
    if NewerRelease(ExeVersion) then
      Result := 'The selected directory contains a newer TransferCove executable (' +
        VersionToStr(ExeVersion) + ').';
end;

function GetFileAttributesW(Path: String): LongWord;
  external 'GetFileAttributesW@kernel32.dll stdcall';

function CreateFileW(Path: String; Access, Share, Security, Creation, Flags: LongWord;
  Template: THandle): THandle; external 'CreateFileW@kernel32.dll stdcall';
function CloseHandle(Handle: THandle): Boolean; external 'CloseHandle@kernel32.dll stdcall';
function RemoveDirectoryW(Path: String): Boolean; external 'RemoveDirectoryW@kernel32.dll stdcall';
function DeleteFileW(Path: String): Boolean; external 'DeleteFileW@kernel32.dll stdcall';

function SafeAttributes(Path: String): LongWord;
var
  Parent: String;
  Error: LongInt;
begin
  Result := $FFFFFFFF;
  Parent := ExtractFileDir(Path);
  if (Length(Parent) > 0) and (Length(Parent) < Length(Path)) then
    if SafeAttributes(Parent) = $FFFFFFFF then Exit;
  Result := GetFileAttributesW(Path);
  if Result = $FFFFFFFF then begin
    Error := DLLGetLastError;
    if (Error <> 2) and (Error <> 3) then RaiseException(SysErrorMessage(Error));
  end else if (Result and $400) <> 0 then begin
    Log('Preserving reparse point: ' + Path);
    Result := $FFFFFFFF;
  end;
end;

procedure ProcessRetiredPath(Path, Hashes: String; Preflight: Boolean);
var
  Attributes: LongWord;
  Handle: THandle;
  Error: LongInt;
begin
  Attributes := SafeAttributes(Path);
  if Attributes = $FFFFFFFF then Exit;
  if Hashes = '' then begin
    if Preflight or ((Attributes and $10) = 0) then Exit;
    if not RemoveDirectoryW(Path) then begin
      Error := DLLGetLastError;
      if (Error <> 145) and (Error <> 2) and (Error <> 3) then
        RaiseException(SysErrorMessage(Error));
    end;
    Exit;
  end;
  if (Attributes and $10) <> 0 then Exit;
  if Pos(',' + Lowercase(GetSHA256OfFile(Path)) + ',', ',' + Hashes + ',') = 0 then begin
    Log('Preserving file with unrecognized content: ' + Path);
    Exit;
  end;
  if Preflight then begin
    if (Attributes and 1) <> 0 then RaiseException('File is read-only');
    { Request DELETE access without marking the file for deletion. }
    Handle := CreateFileW(Path, $10000, 7, 0, 3, $00200000, 0);
    if Handle = THandle(-1) then RaiseException(SysErrorMessage(DLLGetLastError));
    CloseHandle(Handle);
  end else if not DeleteFileW(Path) then
    RaiseException(SysErrorMessage(DLLGetLastError));
end;

procedure CheckPath(RelativePath, Hashes: String; Preflight: Boolean);
var
  Path, Detail: String;
begin
  Path := ExpandConstant('{app}\') + RelativePath;
  try
    ProcessRetiredPath(Path, Hashes, Preflight);
  except
    Detail := Path + ': ' + GetExceptionMessage;
    Log('Upgrade cleanup failed: ' + Detail);
    CleanupErrors := CleanupErrors + #13#10 + Detail;
  end;
end;

procedure CheckRetiredFiles(Preflight: Boolean);
begin
  CleanupErrors := '';
  if not UpgradingInPlace then Exit;
  { Compile only paths that this release has retired. }
#define Inventory FileOpen(AddBackslash(SourcePath) + "released-payload.txt")
#if !Inventory
  #error "Cannot read the released Windows payload inventory"
#endif
#sub EmitCleanup
  #define Line FileRead(Inventory)
  #define Separator Pos("|", Line)
  #define Entry Copy(Line, 1, Separator - 1)
  #if Copy(Entry, Len(Entry), 1) == "\"
    #define Folder Copy(Entry, 1, Len(Entry) - 1)
    #if !DirExists(BuildDir + "\" + Folder)
  CheckPath('{#Folder}', '', Preflight);
    #endif
  #elif !FileExists(BuildDir + "\" + Entry)
  CheckPath('{#Entry}', '{#Copy(Line, Separator + 1, Len(Line))}', Preflight);
  #endif
#endsub
#for {0; !FileEof(Inventory); 0} EmitCleanup
#expr FileClose(Inventory)
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := CheckInstalledVersion;
  if Result <> '' then Exit;
  CheckRetiredFiles(True);
  if CleanupErrors <> '' then
    Result := 'Cannot prepare the upgrade. Resolve these file errors and retry:' + CleanupErrors;
end;

function CleanupSucceeded: Boolean;
begin
  Result := CleanupErrors = '';
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep <> ssPostInstall then Exit;
  CheckRetiredFiles(False);
  if not CleanupSucceeded then
    SuppressibleMsgBox('The new version was installed, but cleanup is incomplete. ' +
      'Resolve these file errors and run Setup again:' + CleanupErrors, mbError, MB_OK, IDOK);
end;

function GetCustomSetupExitCode: Integer;
begin
  if CleanupSucceeded then Result := 0 else Result := 20;
end;
