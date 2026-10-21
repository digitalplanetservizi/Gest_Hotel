param(
    [string]$AdminEmail = 'admin@hoteltempio.local',
    [ValidateRange(1024, 65535)][int]$Port = 18080
)

$ErrorActionPreference = 'Stop'
$projectFolder = Split-Path -Parent $PSScriptRoot
$environmentFile = Join-Path $projectFolder '.env'
if (Test-Path -LiteralPath $environmentFile) {
    Write-Host '.env esiste: configurazione conservata.'
    return
}
if ($AdminEmail -notmatch '^[A-Za-z0-9._+%-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$') {
    throw 'Indica un indirizzo email valido per il primo account.'
}

function New-HotelSecret {
    $bytes = New-Object byte[] 36
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $generator.GetBytes($bytes) } finally { $generator.Dispose() }
    return [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
}

$template = [IO.File]::ReadAllText((Join-Path $projectFolder '.env.example'))
$template = $template.Replace("`r`n", "`n")
$template = $template.Replace('HTTP_PORT=18080', "HTTP_PORT=$Port")
$template = $template.Replace('http://localhost:18080', "http://localhost:$Port")
$template = $template.Replace('http://127.0.0.1:18080', "http://127.0.0.1:$Port")
$template = $template.Replace('POSTGRES_PASSWORD=' + "`n", 'POSTGRES_PASSWORD=' + (New-HotelSecret) + "`n")
$template = $template.Replace('DJANGO_SECRET_KEY=' + "`n", 'DJANGO_SECRET_KEY=' + (New-HotelSecret) + "`n")
$template = $template.Replace('BOOTSTRAP_ADMIN_PASSWORD=' + "`n", 'BOOTSTRAP_ADMIN_PASSWORD=' + (New-HotelSecret) + "`n")
$template = $template.Replace('BOOTSTRAP_ADMIN_EMAIL=admin@hoteltempio.local', "BOOTSTRAP_ADMIN_EMAIL=$AdminEmail")
[IO.File]::WriteAllText($environmentFile, $template, (New-Object System.Text.UTF8Encoding($false)))
Write-Host 'Creato .env con segreti casuali. Le credenziali iniziali sono nel file .env; non condividerlo.'

