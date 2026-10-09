@echo off
REM 아산시 홍보 성과 분석 — 매일 실행 (Windows 작업 스케줄러에 등록)
cd /d "%~dp0"
python run.py daily >> data\daily.log 2>&1
