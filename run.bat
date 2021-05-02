@echo off
chcp 65001

echo 対象のユーザーIDを入力してください
set /p user_id=">>> "
echo 実行前にキャッシュをクリアしますか？(Y/N)
set /p do_cacheclear=">>> "

echo --------------------------------------------------
echo 処理開始
echo ※実行を中止するには Ctrs + C を押してください。
echo

call src\Scripts\activate.bat

if /i {%do_cacheclear%}=={y} (goto :do_refresh)
if /i {%do_cacheclear%}=={Y} (goto :do_refresh)

python src\pxvcrawler.py %user_id%

:do_refresh
python src\pxvcrawler.py %user_id% -r

pause