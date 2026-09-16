#define AppName "OTP LOL"
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef BuildRoot
  #define BuildRoot "."
#endif

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
