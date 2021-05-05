@echo off
chcp 65001

echo 対象のユーザーIDを入力してください
set /p user_id=">>> "
echo 実行前にキャッシュをクリアしますか？(Y/N)
set /p do_cacheclear=">>> "

echo --------------------------------------------------
echo 処理開始

call src\Scripts\activate.bat

if /i {%do_cacheclear%}=={y} (goto :lbl_do_refresh)
if /i {%do_cacheclear%}=={Y} (goto :lbl_do_refresh)

python src\pxv_blkdl.py %user_id%
goto lbl_exit

:lbl_do_refresh
python src\pxv_blkdl.py %user_id% -r
goto lbl_exit

:lbl_exit
echo 処理終了
pause
exit /b 0

