@echo off
echo ================================================
echo  TỐI ƯU DIST - GIẢM DUNG LƯỢNG BUNDLE
echo ================================================
echo.

set DIST=dist\FaceUploadTool\_internal
set BROWSERS=%DIST%\playwright\driver\package\.local-browsers

echo [1/5] Xoa chromium_headless_shell (~258 MB)...
for /D %%d in ("%BROWSERS%\chromium_headless_shell-*") do (
    rmdir /S /Q "%%d"
    echo     Da xoa: %%~nxd
)

echo.
echo [2/5] Xoa ffmpeg (~3 MB)...
for /D %%d in ("%BROWSERS%\ffmpeg-*") do (
    rmdir /S /Q "%%d"
    echo     Da xoa: %%~nxd
)

echo.
echo [3/5] Xoa numpy (khong dung, ~26 MB)...
if exist "%DIST%\numpy" (
    rmdir /S /Q "%DIST%\numpy"
    echo     Da xoa: numpy
)
if exist "%DIST%\numpy.libs" (
    rmdir /S /Q "%DIST%\numpy.libs"
    echo     Da xoa: numpy.libs
)
if exist "%DIST%\numpy-2.4.4.dist-info" (
    rmdir /S /Q "%DIST%\numpy-2.4.4.dist-info"
    echo     Da xoa: numpy dist-info
)
REM Xoa moi phien ban numpy dist-info
for /D %%d in ("%DIST%\numpy-*.dist-info") do (
    rmdir /S /Q "%%d"
    echo     Da xoa: %%~nxd
)

echo.
echo [4/5] Xoa cac package thua khac...
REM psutil
if exist "%DIST%\psutil" (
    rmdir /S /Q "%DIST%\psutil"
    echo     Da xoa: psutil
)
REM yaml
if exist "%DIST%\yaml" (
    rmdir /S /Q "%DIST%\yaml"
    echo     Da xoa: yaml
)

echo.
echo [5/5] Xoa file __pycache__, .pyc test, doc thua...
REM Xoa __pycache__ trong Playwright
for /D /R "%DIST%\playwright" %%d in (__pycache__) do (
    if exist "%%d" rmdir /S /Q "%%d"
)
REM Xoa test folders
for /D /R "%DIST%" %%d in (tests test) do (
    if exist "%%d" rmdir /S /Q "%%d"
)

echo.
echo ================================================
echo  KIEM TRA KICH THUOC
echo ================================================
powershell -ExecutionPolicy Bypass -Command "$p = 'dist\FaceUploadTool'; $sz = (Get-ChildItem -LiteralPath (Join-Path $PWD $p) -Recurse -File | Measure-Object -Property Length -Sum).Sum; Write-Host ('  Tong dist/FaceUploadTool: {0:N0} MB' -f ($sz/1MB))"

echo.
echo ================================================
echo  XONG! San sang nen ZIP de gui.
echo ================================================
pause
