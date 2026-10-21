. (Join-Path $PSScriptRoot 'common.ps1')
Push-Location $ProjectRoot
try { Invoke-HotelDocker compose stop } finally { Pop-Location }
