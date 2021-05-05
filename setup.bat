@echo off
chcp 65001

pip install virtualenv
cd src
virtualenv .
call Scripts\activate.bat
pip install -r requirements.txt

pause