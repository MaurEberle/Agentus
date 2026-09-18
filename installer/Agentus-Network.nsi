Unicode True
RequestExecutionLevel user
SetCompressor /SOLID lzma
AllowRootDirInstall false
ManifestDPIAware true
ShowInstDetails show
ShowUnInstDetails show
SetOverwrite on
CRCCheck on

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"
!include "WordFunc.nsh"
!include "x64.nsh"
!include "generated-version.nsh"

!insertmacro GetParameters
!insertmacro GetOptions
!insertmacro GetTime
!insertmacro VersionCompare

!define PRODUCT_NAME "Agentus Network"
!define PRODUCT_PUBLISHER "Agentus Network"
!define PRODUCT_EXE "AgentusNetwork.exe"
!define REG_UNINSTALL "Software\Microsoft\Windows\CurrentVersion\Uninstall\AgentusNetwork"
!define WEBVIEW2_GUID "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"

Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile "..\dist\Agentus-Network-Setup-${PRODUCT_VERSION}-x64.exe"
InstallDir "$LOCALAPPDATA\Programs\Agentus-Network"
InstallDirRegKey HKCU "${REG_UNINSTALL}" "InstallLocation"
BrandingText "${PRODUCT_NAME}"

VIProductVersion "${PRODUCT_VERSION_QUAD}"
VIAddVersionKey /LANG=1033 "ProductName" "${PRODUCT_NAME}"
VIAddVersionKey /LANG=1033 "CompanyName" "${PRODUCT_PUBLISHER}"
VIAddVersionKey /LANG=1033 "FileDescription" "${PRODUCT_NAME} Setup"
VIAddVersionKey /LANG=1033 "FileVersion" "${PRODUCT_VERSION}"
VIAddVersionKey /LANG=1033 "ProductVersion" "${PRODUCT_VERSION}"
VIAddVersionKey /LANG=1033 "LegalCopyright" "${PRODUCT_PUBLISHER}"

!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_RUN "$INSTDIR\${PRODUCT_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "Agentus Network starten"
!define MUI_COMPONENTSPAGE_SMALLDESC
!define MUI_UNCONFIRMPAGE_TEXT_TOP "Agentus Network wird entfernt. Ollama und WebView2 bleiben installiert. Anwendungsdaten unter LocalAppData\Agentus-Network bleiben standardmäßig erhalten."

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "license.txt"
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "German"

Var KeepData
Var InstallModels

Function .onInit
  SetShellVarContext current
  SetRegView 64
  StrCpy $KeepData "1"
  StrCpy $InstallModels "0"
  ${GetParameters} $0
  ${GetOptions} $0 "/INSTALL_MODELS=" $1
  ${If} $1 == "1"
    StrCpy $InstallModels "1"
  ${EndIf}
  Push $0
  Push "INSTALL_MODELS=1"
  Call StrContains
  Pop $1
  ${If} $1 == "1"
    StrCpy $InstallModels "1"
  ${EndIf}

  ReadRegStr $2 HKCU "${REG_UNINSTALL}" "DisplayVersion"
  ${If} $2 != ""
    ${VersionCompare} $2 "${PRODUCT_VERSION}" $3
    ${If} $3 == 1
      IfSilent +2
      MessageBox MB_OK|MB_ICONSTOP "Eine neuere Version ($2) ist bereits installiert."
      Abort
    ${EndIf}
  ${EndIf}
FunctionEnd

Function .onVerifyInstDir
  StrLen $0 $INSTDIR
  ${If} $0 < 4
    Abort
  ${EndIf}
FunctionEnd

Function StrContains
  Exch $R1
  Exch
  Exch $R2
  Push $R3
  Push $R4
  StrLen $R3 $R1
  StrCpy $R0 0
loop:
  StrCpy $R4 $R2 $R3 $R0
  StrCmp $R4 "" notfound
  StrCmp $R4 $R1 found
  IntOp $R0 $R0 + 1
  Goto loop
found:
  StrCpy $R0 1
  Goto done
notfound:
  StrCpy $R0 0
done:
  Pop $R4
  Pop $R3
  Pop $R2
  Pop $R1
  Exch $R0
FunctionEnd

Function LogLine
  Exch $R0
  Push $R1
  Push $R2
  Push $R3
  Push $R4
  Push $R5
  Push $R6
  Push $R7
  Push $R8
  ${GetTime} "" "L" $R2 $R3 $R4 $R5 $R6 $R7 $R8
  CreateDirectory "$LOCALAPPDATA\Agentus-Network\logs"
  FileOpen $R1 "$LOCALAPPDATA\Agentus-Network\logs\installer.log" a
  FileSeek $R1 0 END
  FileWrite $R1 "$R4-$R3-$R2 $R6:$R7:$R8 $R0$\r$\n"
  FileClose $R1
  DetailPrint $R0
  Pop $R8
  Pop $R7
  Pop $R6
  Pop $R5
  Pop $R4
  Pop $R3
  Pop $R2
  Pop $R1
  Pop $R0
FunctionEnd

Function DetectWebView2
  Push $0
  SetRegView 64
  ReadRegStr $0 HKLM "SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\${WEBVIEW2_GUID}" "pv"
  StrCmp $0 "" 0 present
  ReadRegStr $0 HKCU "SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\${WEBVIEW2_GUID}" "pv"
  StrCmp $0 "" 0 present
  ReadRegStr $0 HKLM "SOFTWARE\Microsoft\EdgeUpdate\Clients\${WEBVIEW2_GUID}" "pv"
  StrCmp $0 "" 0 present
  ReadRegStr $0 HKCU "SOFTWARE\Microsoft\EdgeUpdate\Clients\${WEBVIEW2_GUID}" "pv"
  StrCmp $0 "" missing
present:
  Pop $0
  Push 1
  Return
missing:
  Pop $0
  Push 0
FunctionEnd

Function DetectOllama
  Push $0
  nsExec::ExecToStack 'where ollama.exe'
  Pop $0
  ${If} $0 == 0
    Pop $0
    Push 1
    Return
  ${EndIf}
  Pop $0
  IfFileExists "$LOCALAPPDATA\Ollama\ollama.exe" ollama_yes 0
  IfFileExists "$LOCALAPPDATA\Programs\Ollama\ollama.exe" ollama_yes 0
  Push 0
  Return
ollama_yes:
  Push 1
FunctionEnd

Function WaitOllama
  Push $0
  Push $1
  Push $2
  StrCpy $0 0
wait_loop:
  nsExec::ExecToStack '"$SYSDIR\curl.exe" -s -o NUL --max-time 2 http://127.0.0.1:11434/'
  Pop $1
  Pop $2
  ${If} $1 == 0
    Push "ollama port 11434 ready"
    Call LogLine
    Pop $2
    Pop $1
    Pop $0
    Return
  ${EndIf}
  IntOp $0 $0 + 1
  ${If} $0 >= 60
    Push "ollama port 11434 timeout"
    Call LogLine
    Pop $2
    Pop $1
    Pop $0
    Return
  ${EndIf}
  Sleep 2000
  Goto wait_loop
FunctionEnd

Function StartOllamaIfNeeded
  nsExec::ExecToStack '"$SYSDIR\curl.exe" -s -o NUL --max-time 2 http://127.0.0.1:11434/'
  Pop $0
  Pop $1
  ${If} $0 == 0
    Push "ollama already listening"
    Call LogLine
    Return
  ${EndIf}
  IfFileExists "$LOCALAPPDATA\Ollama\ollama app.exe" start_app 0
  IfFileExists "$LOCALAPPDATA\Ollama\ollama.exe" start_exe 0
  IfFileExists "$LOCALAPPDATA\Programs\Ollama\ollama.exe" start_prog 0
  Push "ollama exe not found to start"
  Call LogLine
  Return
start_app:
  Push "starting ollama app.exe --hide --fast-startup"
  Call LogLine
  nsExec::ExecToLog 'powershell -NoProfile -WindowStyle Hidden -Command "Start-Process -FilePath ([IO.Path]::Combine($$env:LOCALAPPDATA,''Ollama'',''ollama app.exe'')) -ArgumentList ''--hide'',''--fast-startup'' -WindowStyle Hidden"'
  Return
start_exe:
  Push "starting ollama serve"
  Call LogLine
  nsExec::ExecToLog 'powershell -NoProfile -WindowStyle Hidden -Command "Start-Process -FilePath ([IO.Path]::Combine($$env:LOCALAPPDATA,''Ollama'',''ollama.exe'')) -ArgumentList ''serve'' -WindowStyle Hidden"'
  Return
start_prog:
  Push "starting Programs\\Ollama serve"
  Call LogLine
  nsExec::ExecToLog 'powershell -NoProfile -WindowStyle Hidden -Command "Start-Process -FilePath ([IO.Path]::Combine($$env:LOCALAPPDATA,''Programs'',''Ollama'',''ollama.exe'')) -ArgumentList ''serve'' -WindowStyle Hidden"'
FunctionEnd

Section "Anwendungsdateien" SecApp
  SectionIn RO
  Push "install app ${PRODUCT_VERSION}"
  Call LogLine
  nsExec::ExecToLog 'taskkill /IM ${PRODUCT_EXE} /F'
  SetOutPath $INSTDIR
  SetOverwrite on
  File /r "..\dist\AgentusNetwork\*.*"
  CreateDirectory "$LOCALAPPDATA\Agentus-Network"
  CreateDirectory "$LOCALAPPDATA\Agentus-Network\data"
  CreateDirectory "$LOCALAPPDATA\Agentus-Network\logs"
  WriteUninstaller "$INSTDIR\uninst.exe"
  WriteRegStr HKCU "${REG_UNINSTALL}" "DisplayName" "${PRODUCT_NAME}"
  WriteRegStr HKCU "${REG_UNINSTALL}" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr HKCU "${REG_UNINSTALL}" "Publisher" "${PRODUCT_PUBLISHER}"
  WriteRegStr HKCU "${REG_UNINSTALL}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${REG_UNINSTALL}" "DisplayIcon" "$INSTDIR\${PRODUCT_EXE}"
  WriteRegStr HKCU "${REG_UNINSTALL}" "UninstallString" '"$INSTDIR\uninst.exe"'
  WriteRegDWORD HKCU "${REG_UNINSTALL}" "NoModify" 1
  WriteRegDWORD HKCU "${REG_UNINSTALL}" "NoRepair" 1
SectionEnd

Section "Startmenü-Verknüpfung" SecStart
  CreateDirectory "$SMPROGRAMS\${PRODUCT_NAME}"
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_NAME}.lnk" "$INSTDIR\${PRODUCT_EXE}"
SectionEnd

Section /o "Desktop-Verknüpfung" SecDesktop
  CreateShortCut "$DESKTOP\${PRODUCT_NAME}.lnk" "$INSTDIR\${PRODUCT_EXE}"
SectionEnd

Section "WebView2 (falls fehlend)" SecWebView
  Call DetectWebView2
  Pop $0
  ${If} $0 == 1
    Push "webview2 present"
    Call LogLine
  ${Else}
    Push "webview2 missing, running bootstrapper"
    Call LogLine
    InitPluginsDir
    SetOutPath "$PLUGINSDIR"
    File "vendor\MicrosoftEdgeWebview2Setup.exe"
    nsExec::ExecToLog '"$PLUGINSDIR\MicrosoftEdgeWebview2Setup.exe" /silent /install'
    Pop $1
    Push "webview2 bootstrapper exit $1"
    Call LogLine
    ${If} $1 != 0
      IfSilent +2
      MessageBox MB_OK|MB_ICONEXCLAMATION "WebView2-Runtime konnte nicht installiert werden (Exit $1). Die App-Dateien bleiben. Der Host zeigt host.webview2.missing."
    ${EndIf}
  ${EndIf}
SectionEnd

Section "Ollama (falls fehlend)" SecOllama
  Call DetectOllama
  Pop $0
  ${If} $0 == 1
    Push "ollama present"
    Call LogLine
  ${Else}
    Push "ollama missing, download + silent setup"
    Call LogLine
    InitPluginsDir
    SetOutPath "$PLUGINSDIR"
    File "fetch-url.ps1"
    nsExec::ExecToLog '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "$PLUGINSDIR\fetch-url.ps1" -Url "${OLLAMA_URL}" -OutFile "$TEMP\${OLLAMA_NAME}" -Sha256 "${OLLAMA_SHA256}"'
    Pop $1
    Push "ollama download exit $1"
    Call LogLine
    IfFileExists "$TEMP\${OLLAMA_NAME}" 0 ollama_skip
    nsExec::ExecToLog '"$TEMP\${OLLAMA_NAME}" /SP- /VERYSILENT /NORESTART'
    Pop $1
    Push "OllamaSetup exit $1"
    Call LogLine
    ${If} $1 != 0
      IfSilent +2
      MessageBox MB_OK|MB_ICONEXCLAMATION "Ollama-Setup endete mit Exit $1. Die App-Dateien bleiben. Die Dashboard-Setup-Karte zeigt den Runtime-Status."
    ${EndIf}
    ollama_skip:
  ${EndIf}
  Call StartOllamaIfNeeded
  Call WaitOllama
SectionEnd

Section "Standardmodelle pullen" SecModels
  IfSilent 0 do_model_pull
    ${If} $InstallModels != "1"
      Push "silent: skip model pulls"
      Call LogLine
      Goto models_done
    ${EndIf}
  do_model_pull:
  Push "ollama pull nomic-embed-text + llama3.2:1b"
  Call LogLine
  nsExec::ExecToLog 'ollama pull nomic-embed-text'
  Pop $1
  ${If} $1 != 0
    Push "ollama pull nomic-embed-text exit $1"
    Call LogLine
  ${EndIf}
  nsExec::ExecToLog 'ollama pull llama3.2:1b'
  Pop $1
  ${If} $1 != 0
    Push "ollama pull llama3.2:1b exit $1"
    Call LogLine
  ${EndIf}
models_done:
SectionEnd

Section "Uninstall"
  nsExec::ExecToLog 'taskkill /IM ${PRODUCT_EXE} /F'
  Delete "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_NAME}.lnk"
  RMDir "$SMPROGRAMS\${PRODUCT_NAME}"
  Delete "$DESKTOP\${PRODUCT_NAME}.lnk"
  DeleteRegKey HKCU "${REG_UNINSTALL}"
  RMDir /r "$INSTDIR"
  ${If} $KeepData != "1"
    RMDir /r "$LOCALAPPDATA\Agentus-Network"
  ${EndIf}
SectionEnd

Function un.onInit
  SetShellVarContext current
  SetRegView 64
  StrCpy $KeepData "1"
  IfSilent keep_silent
  MessageBox MB_YESNO|MB_ICONQUESTION|MB_DEFBUTTON1 "Anwendungsdaten behalten? (Empfohlen: Ja)$\r$\n$\r$\nNein löscht config.yaml, data und Logs unter LocalAppData\Agentus-Network. Ollama und WebView2 bleiben." IDNO drop_data
  StrCpy $KeepData "1"
  Goto keep_silent
drop_data:
  StrCpy $KeepData "0"
keep_silent:
FunctionEnd

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SecApp} "Agentus Network Anwendung"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecStart} "Startmenü"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecDesktop} "Desktop-Verknüpfung"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecWebView} "WebView2 Evergreen, falls fehlend"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecOllama} "Offizielles Ollama-Setup, falls fehlend"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecModels} "nomic-embed-text und llama3.2:1b"
!insertmacro MUI_FUNCTION_DESCRIPTION_END
