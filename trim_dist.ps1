$base = $PSScriptRoot
$browsersPath = Join-Path $base "dist\FaceUploadTool\_internal\playwright\driver\package"
$localBrowsers = $browsersPath + "\.local-browsers"

Write-Host "[1] Xoa chromium_headless_shell..."
$headlessDir = Join-Path $localBrowsers "chromium_headless_shell-1208"
if (Test-Path -LiteralPath $headlessDir) {
    Remove-Item -LiteralPath $headlessDir -Recurse -Force
    Write-Host "    OK! ~258 MB da xoa"
} else {
    Write-Host "    Khong tim thay"
}

Write-Host "[2] Xoa ffmpeg..."
$ffmpegDir = Join-Path $localBrowsers "ffmpeg-1011"
if (Test-Path -LiteralPath $ffmpegDir) {
    Remove-Item -LiteralPath $ffmpegDir -Recurse -Force
    Write-Host "    OK! ~3 MB da xoa"
} else {
    Write-Host "    Khong tim thay"
}

Write-Host ""
Write-Host "Kiem tra kich thuoc sau khi don..."
$distFolder = Join-Path $base "dist\FaceUploadTool"
$sz = (Get-ChildItem -LiteralPath $distFolder -Recurse -File | Measure-Object -Property Length -Sum).Sum
Write-Host ("Tong dist/FaceUploadTool: {0:N0} MB" -f ($sz/1MB))
Write-Host "XONG!"
