Set-Location -LiteralPath "D:\KAS_APP_GITHUB\KAS_APP-main\KAS_APP-main"
& "D:\KAS_APP_GITHUB\KAS_APP-main\KAS_APP-main\.venv\Scripts\python.exe" "D:\KAS_APP_GITHUB\KAS_APP-main\KAS_APP-main\.codex_run_kas.py" *>&1 | Tee-Object -FilePath "D:\KAS_APP_GITHUB\KAS_APP-main\KAS_APP-main\flask.host.log"
