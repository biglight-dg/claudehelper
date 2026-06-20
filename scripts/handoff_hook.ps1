# 세션당 한 번만 handoff.md를 출력 (PID 기반으로 새 세션 감지)
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$markerFile = "$env:TEMP\claude_handoff_$PID.marker"
$handoffPath = "C:\Users\chris\Claude\Projects\claudehelper\handoff.md"

if (-not (Test-Path $markerFile)) {
    New-Item -Path $markerFile -ItemType File -Force | Out-Null

    if (Test-Path $handoffPath) {
        Write-Output ""
        Write-Output "=========================================="
        Write-Output "  [HANDOFF] 이전 작업 내용을 불러왔습니다"
        Write-Output "=========================================="
        Get-Content $handoffPath -Encoding UTF8
        Write-Output "=========================================="
        Write-Output ""
    }
}

exit 0
