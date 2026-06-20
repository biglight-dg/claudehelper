# 매주 AI 뉴스 통합 브리핑(뉴닉 스타일) 자동 생성 래퍼
# Windows 작업 스케줄러가 매주 월요일 실행한다. claude CLI를 권한 자동승인 모드로 헤드리스 호출.
$ErrorActionPreference = "Continue"
# claude는 UTF-8로 출력하므로 콘솔/파이프 인코딩을 UTF-8로 맞춰 로그 깨짐 방지
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$proj = "C:\Users\chris\Claude\Projects\claudehelper"
$claude = "C:\Users\chris\.local\bin\claude.exe"
$log = "C:\Users\chris\.claude\weekly_digest.log"

Set-Location $proj
"`n===== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') 주간 브리핑 시작 =====" | Out-File -FilePath $log -Append -Encoding utf8

$prompt = @'
매주 AI 뉴스 통합 브리핑(뉴닉 스타일)을 자동 생성하라. CLAUDE.md의 "최근 뉴스 & 주간 브리핑" 절차를 따른다. 한글이 들어간 파이썬은 임시 .py 파일로 작성해 codex 런타임 파이썬(C:\Users\chris\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe, PYTHONIOENCODING=utf-8)으로 실행한다.

절차:
0) tools.news.collect_news() 로 최신 뉴스를 먼저 수집(기록)한다.
1) tools.news.build_digest_source(7) 로 최근 항목과 ids·period를 확보한다.
2) 전 소스에서 핵심 3건을 선정하고, 각 기사 링크를 tools.reader.fetch_url(또는 just-scrape 스킬)로 원문 전문을 보강해 여러 문단으로 길게 쓴다. 각 핵심에 인사이트를 이끄는 "생각해볼 질문" 1개를 포함한다.
3) 자투리 뉴스 10건(title, blurb는 1~2문장으로 충실히 써서 클릭 없이도 이해되게, source, link), 필요 기술/개념(skills), 이번 주 공부거리(study)를 작성한다. 대상은 비개발 실무자, 톤은 친근+비유.
4) 구조화 dict 구성: {title, period, intro, deep_dives[3]{emoji,title,body,question,sources[{name,url}]}, shorts[~10]{title,blurb,source,link}, skills[], study[]}
5) tools.news.save_digest(digest, ids) 를 호출한다(ids는 build_digest_source 결과의 ids).
6) 완료 후 무엇을 핵심 3건으로 골랐는지 한 줄로 요약 보고한다.
'@

$prompt | & $claude -p --dangerously-skip-permissions 2>&1 | Out-File -FilePath $log -Append -Encoding utf8
"===== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') 종료 (exit=$LASTEXITCODE) =====" | Out-File -FilePath $log -Append -Encoding utf8
