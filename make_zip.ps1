$base = $PSScriptRoot
$source = Join-Path $base "dist\FaceUploadTool"
$dest   = Join-Path $base "dist\FaceUploadTool.zip"

if (Test-Path -LiteralPath $dest) {
    Remove-Item -LiteralPath $dest -Force
}

Write-Host "Dang nen ZIP..."
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($source, $dest, 'Optimal', $true)

$zipSize = (Get-Item -LiteralPath $dest).Length
Write-Host ("Zip hoan thanh: {0:N0} MB -> {1}" -f ($zipSize/1MB), $dest)
