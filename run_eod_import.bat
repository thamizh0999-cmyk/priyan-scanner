@echo off
cd /d C:\Users\Hp\Desktop\market
venv\Scripts\python.exe manage.py import_nse >> logs\eod_import.log 2>&1
