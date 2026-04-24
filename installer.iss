#define MyAppName "Screenshot Tool"
#define MyAppPublisher "ATS Inc."
#define MyAppExeName "ScreenshotTool.exe"
#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL=https://github.com/JustinGlave/Screenshot_Tool
AppSupportURL=https://github.com/JustinGlave/Screenshot_Tool/issues
AppUpdatesURL=https://github.com/JustinGlave/Screenshot_Tool/releases

; Install to LocalAppData — no admin rights needed, auto-updater can write here
DefaultDirName={localappdata}\ATS Inc\Screenshot Tool
DefaultGroupName=ATS Inc\Screenshot Tool
DisableProgramGroupPage=yes

; Output
OutputDir=dist
OutputBaseFilename=ScreenshotToolSetup
SetupIconFile=screenshot_tool_icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

; No admin required
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline

; Compression
Compression=lzma2/ultra64
SolidCompression=yes

; Wizard
WizardStyle=modern
WizardResizable=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "dist\ScreenshotTool\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userdesktop}\{#MyAppName}";     Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\{#MyAppName}";           Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
