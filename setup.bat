@echo off
chcp 65001

pip install virtualenv
call src\Scripts\activate.bat
pip install -r src\requirements.txt

pause