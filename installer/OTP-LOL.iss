#define AppName "OTP LOL"
#ifndef AppVersion
  #define AppVersion "11.1"
#endif
#ifndef BuildRoot
  #define BuildRoot "."
#endif
#define WebView2DownloadUrl "https://developer.microsoft.com/microsoft-edge/webview2/"

[Setup]
AppId={{C96CBB4F-54A6-4BA3-BD67-9D2F8EF7CF4B}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=OTP LOL
DefaultDirName={autopf}\OTP LOL
DisableProgramGroupPage=yes
OutputDir={#BuildRoot}\release
OutputBaseFilename=OTP-LOL-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\OTP LOL.exe

[Files]
Source: "{#BuildRoot}\OTP LOL\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\OTP LOL"; Filename: "{app}\OTP LOL.exe"; WorkingDir: "{app}"
Name: "{autoprograms}\OTP LOL"; Filename: "{app}\OTP LOL.exe"; WorkingDir: "{app}"

[Run]
Filename: "{app}\OTP LOL.exe"; Description: "Lancer OTP LOL"; Flags: nowait postinstall skipifsilent

[Code]
const
  WebView2EvergreenClientGuid = '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';

function IsValidWebView2Version(const Version: String): Boolean;
var
  Index, PartCount, DigitsInPart: Integer;
begin
  Result := False;
  if Version = '' then
    exit;

  PartCount := 1;
  DigitsInPart := 0;
  for Index := 1 to Length(Version) do begin
    if Version[Index] = '.' then begin
      if DigitsInPart = 0 then
        exit;
      Inc(PartCount);
      DigitsInPart := 0;
    end else begin
      if (Version[Index] < '0') or (Version[Index] > '9') then
        exit;
      Inc(DigitsInPart);
    end;
  end;

  Result := (DigitsInPart > 0) and (PartCount = 4) and (Version <> '0.0.0.0');
end;

function HasWebView2Value(RootKey: Integer; const KeyPath: String): Boolean;
var
  Version: String;
begin
  Result := False;
  if not RegQueryStringValue(RootKey, KeyPath, 'pv', Version) then
    exit;
  Result := IsValidWebView2Version(Trim(Version));
end;

function HasWebView2Client(RootKey: Integer): Boolean;
begin
  Result := HasWebView2Value(
    RootKey,
    'Software\Microsoft\EdgeUpdate\Clients\' + WebView2EvergreenClientGuid
  ) or HasWebView2Value(
    RootKey,
    'Software\WOW6432Node\Microsoft\EdgeUpdate\Clients\' + WebView2EvergreenClientGuid
  );
end;

function HasWebView2Runtime: Boolean;
begin
  Result := HasWebView2Client(HKCU) or HasWebView2Client(HKLM);
  if (not Result) and IsWin64 then begin
    Result :=
      HasWebView2Client(HKCU64) or HasWebView2Client(HKLM64);
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ErrorCode: Integer;
begin
  Result := '';
  if HasWebView2Runtime then
    exit;

  if MsgBox(
    'Microsoft Edge WebView2 Evergreen Runtime est requis pour OTP LOL.' + #13#10#13#10 +
    'L''installateur va ouvrir la page officielle pour vous permettre de l''installer.' + #13#10#13#10 +
    'Après installation, relancez cet installateur.',
    mbError,
    MB_OKCANCEL
  ) = IDOK then
    ShellExec(
      'open',
      '{#WebView2DownloadUrl}',
      '',
      '',
      SW_SHOWNORMAL,
      ewNoWait,
      ErrorCode
    );
  Result := 'Microsoft Edge WebView2 Evergreen Runtime est manquant. Installez-le puis relancez l''installateur.';
end;
