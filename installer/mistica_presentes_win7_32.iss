#define MyAppName "Mistica Presentes"
#define MyAppVersion "1.0.1"
#define MyAppPublisher "Mistica Presentes"
#define MyAppExeName "MisticaPresentes.exe"

[Setup]
AppId={{7D9A2E2F-0C6B-4C5E-8A19-4D4953544943}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Mistica Presentes
DefaultGroupName=Mistica Presentes
DisableProgramGroupPage=yes
OutputDir=..\dist\installer
OutputBaseFilename=MisticaPresentes-Win7-32bit-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x86 x64
ArchitecturesInstallIn64BitMode=
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na area de trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked

[Files]
Source: "..\dist\MisticaPresentes\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Mistica Presentes"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Mistica Presentes"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir Mistica Presentes"; Flags: nowait postinstall skipifsilent
