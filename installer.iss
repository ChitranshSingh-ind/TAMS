; Inno Setup Script for TAMS Desktop Application and CoachingHelper Companion
; Generates standard Windows installer: Output/TAMS_Setup_v1.0.5.exe

#define MyAppName "TAMS"
#define MyAppVersion "1.0.5"
#define MyAppPublisher "Chitransh Singh"
#define MyAppURL "https://github.com/ChitranshSingh-ind/TAMS"
#define MyAppExeName "TAMS.exe"
#define MyHelperExeName "CoachingHelper.exe"

[Setup]
; Unique GUID identifying this application
AppId={{E8F91A23-9B67-4DF2-B4E5-68A1C52E9901}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DisableProgramGroupPage=yes
DefaultGroupName={#MyAppName}
OutputDir=Output
OutputBaseFilename=TAMS_Setup_v{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=app\resources\icons\app_icon.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}:"; Flags: unchecked
Name: "autostarthelper"; Description: "Launch CoachingHelper companion automatically at Windows startup"; GroupDescription: "Background Automation:"

[Files]
; Copy all binaries, Qt libraries, and database migrations from PyInstaller output
Source: "dist\TAMS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autoprograms}\CoachingHelper"; Filename: "{app}\{#MyHelperExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; Configure optional Windows login autostart for CoachingHelper
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "TAMS CoachingHelper"; ValueData: """{app}\{#MyHelperExeName}"""; Flags: uninsdeletevalue; Tasks: autostarthelper

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall
Filename: "{app}\{#MyHelperExeName}"; Description: "Start CoachingHelper companion in system tray"; Flags: nowait postinstall skipifsilent; Tasks: autostarthelper
