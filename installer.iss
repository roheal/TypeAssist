; installer.iss - Inno Setup script for TypeAssist
[Setup]
AppId={{AB745D0B-E0FF-4167-B8B9-288D11B49568}}
AppName=TypeAssist
AppVersion=1.0
AppPublisher=roheal
AppPublisherURL=https://github.com/roheal/AutoType
AppSupportURL=https://github.com/roheal/AutoType
AppUpdatesURL=https://github.com/roheal/AutoType
DefaultDirName={autopf}\TypeAssist
DefaultGroupName=TypeAssist
OutputBaseFilename=TypeAssist_Installer
Compression=lzma
SolidCompression=yes
SetupIconFile=typeassist.ico
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Include main app files ONLY (no python-installer.exe)
Source: "main.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "run_app.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "typeassist.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\TypeAssist"; Filename: "{app}\run_app.bat"; WorkingDir: "{app}"; IconFilename: "{app}\typeassist.ico"
Name: "{autodesktop}\TypeAssist"; Filename: "{app}\run_app.bat"; Tasks: desktopicon; WorkingDir: "{app}"; IconFilename: "{app}\typeassist.ico"
Name: "{group}\{cm:UninstallProgram,TypeAssist}"; Filename: "{uninstallexe}"

[Run]
; Install dependencies after Python is available
Filename: "python"; Parameters: "-m pip install --upgrade pip"; Flags: runhidden waituntilterminated; StatusMsg: "Upgrading pip..."; Check: IsPythonInstalled
Filename: "python"; Parameters: "-m pip install -r ""{app}\requirements.txt"""; Flags: runhidden waituntilterminated; StatusMsg: "Installing Python dependencies..."; Check: IsPythonInstalled

; Launch the app after installation
Filename: "{app}\run_app.bat"; Description: "{cm:LaunchProgram,TypeAssist}"; Flags: nowait skipifsilent; Check: IsPythonInstalled

; --------- Custom Pascal code to detect python ----------
[Code]
function IsPythonInstalled(): Boolean;
var
  ResultCode: Integer;
begin
  { try 'python --version' silently; return true if success }
  if Exec(ExpandConstant('{cmd}'), '/C python --version >nul 2>&1', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    Result := (ResultCode = 0);
  end
  else
    Result := False;
end;

function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
begin
  // Check for Python at the beginning
  if not IsPythonInstalled() then
  begin
    if MsgBox(
      'Python is not detected on your system.' + #13#10 + #13#10 +
      'TypeAssist requires Python 3.6 or newer to run.' + #13#10 + #13#10 +
      'Please:' + #13#10 +
      '1. Install Python from python.org' + #13#10 +
      '2. Make sure to check "Add Python to PATH"' + #13#10 +
      '3. Then run this installer again' + #13#10 + #13#10 +
      'Click OK to open python.org now, or Cancel to exit.',
      mbError, MB_OKCANCEL) = IDOK then
    begin
      // Open Python download page
      ShellExec('open', 'https://www.python.org/downloads/', '', '', SW_SHOW, ewNoWait, ResultCode);
    end;
    Result := False;  // Stop installation
  end
  else
    Result := True;   // Continue installation
end;