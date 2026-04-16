@echo off
echo ================================================
echo  TỐI ƯU DIST - XOÁ BROWSER KHÔNG CẦN THIẾT
echo ================================================
echo.

set BROWSERS_PATH=dist\FaceUploadTool\_internal\playwright\driver\package\.local-browsers

echo [1] Xoá chromium_headless_shell (không dùng headless mode)...
if exist "%BROWSERS_PATH%\chromium_headless_shell-1208" (
    rmdir /S /Q "%BROWSERS_PATH%\chromium_headless_shell-1208"
    echo     Done! Tiết kiệm ~258 MB
) else (
    echo     Không tìm thấy (đã xoá rồi?)
)

echo.
echo [2] Xoá ffmpeg (không cần video capture)...
if exist "%BROWSERS_PATH%\ffmpeg-1011" (
    rmdir /S /Q "%BROWSERS_PATH%\ffmpeg-1011"
    echo     Done! Tiết kiệm ~3 MB
) else (
    echo     Không tìm thấy
)

echo.
echo [3] Kiểm tra kích thước sau khi dọn...
powershell -ExecutionPolicy Bypass -Command "$p = 'dist\FaceUploadTool'; $sz = (Get-ChildItem -LiteralPath (Join-Path $PWD $p) -Recurse -File | Measure-Object -Property Length -Sum).Sum; Write-Host ('  Tổng dist/FaceUploadTool: {0:N0} MB' -f ($sz/1MB))"

echo.
echo ================================================
echo  XONG! Bây giờ có thể nén ZIP để gửi.
echo ================================================
pause
