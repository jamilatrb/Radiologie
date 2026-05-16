#define MyAppName "Gestion des rendez-vous de radiologie"
#define MyAppExeName "GestionRadiologie.exe"
#define MyAppVersion "1.2.0"
#define MyPublisher "Radiologie"

[Setup]
AppId={{D8DAD9B0-1B0A-4E54-9B88-6EAB16AECC16}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyPublisher}
DefaultDirName={localappdata}\GestionRadiologie
DefaultGroupName={#MyAppName}
DisableDirPage=no
AllowNoIcons=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
WizardStyle=modern
Compression=lzma
SolidCompression=yes
OutputDir=installer
OutputBaseFilename=Setup_GestionRadiologie
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau"; GroupDescription: "Raccourcis :"; Flags: unchecked

[Files]
Source: "release\GestionRadiologie.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "release\patients.db"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "release\README.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; WorkingDir: "{app}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Lancer {#MyAppName}"; Flags: nowait postinstall skipifsilent
