Set-Location -LiteralPath "D:\KAS_APP"
& "D:\KAS_APP\.venv\Scripts\python.exe" "D:\KAS_APP\.codex_run_kas.py" *>&1 | Tee-Object -FilePath "D:\KAS_APP\flask.host.log"
