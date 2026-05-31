#define MyAppName "Myna"
#define MyAppVersion GetEnv("MYNA_VERSION")
#define MyAppPublisher "uskyu"
#define MyAppURL "https://github.com/uskyu/myna"
#define MyAppExeName "Myna.bat"
#define MyDistDir GetEnv("MYNA_DIST_DIR")
#define MyOutputDir GetEnv("MYNA_OUTPUT_DIR")

#if MyAppVersion == ""
#define MyAppVersion "dev"
#endif

[Setup]
AppId={{8D730F34-845C-44F7-A5DB-4E868FD9A14D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile={#MyDistDir}\LICENSE
OutputDir={#MyOutputDir}
OutputBaseFilename=Myna-Setup-x64
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}
WizardResizable=yes
UsePreviousAppDir=yes
UsePreviousGroup=yes
ShowLanguageDialog=no

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Languages]
Name: "chinesesimplified"; MessagesFile: "ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "{#MyDistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Myna"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\关闭 Myna"; Filename: "{app}\scripts\windows\stop-myna.bat"; WorkingDir: "{app}"
Name: "{autodesktop}\Myna"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动 Myna"; Flags: nowait postinstall skipifsilent
