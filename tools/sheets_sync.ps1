# Sync curriculum / knowledge / source index to Google Sheets.
# Run weekly by Windows Task Scheduler, right after the Monday news digest.
# NOTE: keep this file ASCII-only. PowerShell 5.1 mis-decodes a BOM-less
# UTF-8 script as CP949, which corrupts parsing. Korean lives in the
# Python output only, written to the log as UTF-8.
$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

$proj = "C:\Users\chris\Claude\Projects\claudehelper"
# codex runtime python where claudehelper deps (gspread, etc.) are installed
$py  = "C:\Users\chris\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$log = "C:\Users\chris\.claude\sheets_sync.log"

Set-Location $proj
"`n===== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') sheet sync start =====" | Out-File -FilePath $log -Append -Encoding utf8

# Put 2>&1 on an assignment (not a pipeline) to avoid a PS 5.1 parser error.
$out = & $py "tools\gsheet_sync.py" 2>&1
$code = $LASTEXITCODE
$out | Out-File -FilePath $log -Append -Encoding utf8

"===== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') done (exit=$code) =====" | Out-File -FilePath $log -Append -Encoding utf8
