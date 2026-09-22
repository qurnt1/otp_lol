#define AppName "OTP LOL"
#ifndef AppVersion
  #define AppVersion "11.0"
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
  WebView2ClientGuid1 = '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  WebView2ClientGuid2 = '{2CD8A007-E189-409D-A2C8-9AF4EF3C72AA}';
  WebView2ClientGuid3 = '{0D50BFEC-CD6A-4F9A-964C-C7416E3ACB10}';
  WebView2ClientGuid4 = '{65C35B14-6C1D-4122-AC46-7148CC9D6497}';

function HasWebView2Value(RootKey: Integer; const KeyPath: String): Boolean;
var
  Version: String;
begin
  Result := RegQueryStringValue(RootKey, KeyPath, 'pv', Version) and
    (Trim(Version) <> '') and (Version <> '0.0.0.0');
end;

function HasWebView2Client(RootKey: Integer; const ClientGuid: String): Boolean;
begin
  Result := HasWebView2Value(
    RootKey,
    'Software\Microsoft\EdgeUpdate\Clients\' + ClientGuid
  ) or HasWebView2Value(
    RootKey,
    'Software\WOW6432Node\Microsoft\EdgeUpdate\Clients\' + ClientGuid
  );
end;

function HasWebView2Runtime: Boolean;
begin
  Result :=
    HasWebView2Client(HKCU, WebView2ClientGuid1) or
    HasWebView2Client(HKCU, WebView2ClientGuid2) or
    HasWebView2Client(HKCU, WebView2ClientGuid3) or
    HasWebView2Client(HKCU, WebView2ClientGuid4) or
    HasWebView2Client(HKLM, WebView2ClientGuid1) or
    HasWebView2Client(HKLM, WebView2ClientGuid2) or
    HasWebView2Client(HKLM, WebView2ClientGuid3) or
    HasWebView2Client(HKLM, WebView2ClientGuid4);
  if (not Result) and IsWin64 then begin
    Result :=
      HasWebView2Client(HKCU64, WebView2ClientGuid1) or
      HasWebView2Client(HKCU64, WebView2ClientGuid2) or
      HasWebView2Client(HKCU64, WebView2ClientGuid3) or
      HasWebView2Client(HKCU64, WebView2ClientGuid4) or
      HasWebView2Client(HKLM64, WebView2ClientGuid1) or
      HasWebView2Client(HKLM64, WebView2ClientGuid2) or
      HasWebView2Client(HKLM64, WebView2ClientGuid3) or
      HasWebView2Client(HKLM64, WebView2ClientGuid4);
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
