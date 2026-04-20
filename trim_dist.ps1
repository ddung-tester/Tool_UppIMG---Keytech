$base = $PSScriptRoot
$dist = Join-Path $base "dist\FaceUploadTool\_internal"
$browsersPath = Join-Path $dist "playwright\driver\package\.local-browsers"

Write-Host "================================================"
Write-Host " TOI UU DIST - GIAM DUNG LUONG BUNDLE"
Write-Host "================================================"
Write-Host ""

# [1] Xoa chromium_headless_shell (~258 MB)
Write-Host "[1/5] Xoa chromium_headless_shell..."
Get-ChildItem $browsersPath -Directory -Filter "chromium_headless_shell-*" -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item $_.FullName -Recurse -Force
    Write-Host "    Da xoa: $($_.Name)"
}

# [2] Xoa ffmpeg (~3 MB)
Write-Host "[2/5] Xoa ffmpeg..."
Get-ChildItem $browsersPath -Directory -Filter "ffmpeg-*" -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item $_.FullName -Recurse -Force
    Write-Host "    Da xoa: $($_.Name)"
}

# [3] Xoa numpy (~26 MB) — khong dung trong code
Write-Host "[3/5] Xoa numpy..."
@("numpy", "numpy.libs") | ForEach-Object {
    $p = Join-Path $dist $_
    if (Test-Path $p) { Remove-Item $p -Recurse -Force; Write-Host "    Da xoa: $_" }
}
Get-ChildItem $dist -Directory -Filter "numpy-*.dist-info" -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item $_.FullName -Recurse -Force
    Write-Host "    Da xoa: $($_.Name)"
}

# [4] Xoa package thua khac
Write-Host "[4/5] Xoa package thua..."
@("psutil", "yaml", "greenlet") | ForEach-Object {
    $p = Join-Path $dist $_
    if (Test-Path $p) { Remove-Item $p -Recurse -Force; Write-Host "    Da xoa: $_" }
}

# [5] Xoa __pycache__ va test folders
Write-Host "[5/5] Xoa __pycache__ va test folders..."
Get-ChildItem $dist -Directory -Recurse -Filter "__pycache__" -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item $_.FullName -Recurse -Force
}
Get-ChildItem $dist -Directory -Recurse | Where-Object { $_.Name -in @("tests", "test") } | ForEach-Object {
    Remove-Item $_.FullName -Recurse -Force
    Write-Host "    Da xoa: $($_.FullName.Replace($dist, ''))"
}

Write-Host ""
Write-Host "================================================"
Write-Host " KIEM TRA KICH THUOC"
Write-Host "================================================"
$distFolder = Join-Path $base "dist\FaceUploadTool"
$sz = (Get-ChildItem -LiteralPath $distFolder -Recurse -File | Measure-Object -Property Length -Sum).Sum
Write-Host ("  Tong dist/FaceUploadTool: {0:N0} MB" -f ($sz/1MB))
Write-Host ""
Write-Host "XONG! San sang nen ZIP."
