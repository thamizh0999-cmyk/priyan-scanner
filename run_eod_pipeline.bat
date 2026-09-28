@echo off
cd /d C:\Users\Hp\Desktop\market

venv\Scripts\python.exe manage.py run_eod_pipeline >> logs\eod_pipeline.log 2>&1
