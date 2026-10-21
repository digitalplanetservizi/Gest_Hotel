param(
    [string]$AdminEmail = 'admin@hoteltempio.local',
    [ValidateRange(1024, 65535)][int]$Port = 18080
)

. (Join-Path $PSScriptRoot 'common.ps1')
Push-Location $ProjectRoot
try {
    & (Join-Path $PSScriptRoot 'setup.ps1') -AdminEmail $AdminEmail -Port $Port
    Invoke-HotelDocker compose config --quiet
    Invoke-HotelDocker compose up -d --wait database
    Invoke-HotelDocker compose build backend frontend
    Invoke-HotelDocker compose run --rm --no-deps backend python manage.py migrate --noinput
    Invoke-HotelDocker compose run --rm --no-deps backend python manage.py bootstrap
    Invoke-HotelDocker compose up -d --wait
    Write-Host 'Servizi avviati. Apri localhost sulla HTTP_PORT configurata in .env.'
    Write-Host 'Credenziali iniziali: BOOTSTRAP_ADMIN_EMAIL e BOOTSTRAP_ADMIN_PASSWORD in .env.'
} finally { Pop-Location }

