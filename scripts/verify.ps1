. (Join-Path $PSScriptRoot 'common.ps1')
Push-Location $ProjectRoot
try {
    Invoke-HotelDocker compose config --quiet
    Invoke-HotelDocker compose exec -T backend python manage.py check
    Invoke-HotelDocker compose exec -T backend python manage.py makemigrations --check --dry-run
    Invoke-HotelDocker compose exec -T backend python manage.py test --noinput
    Invoke-HotelDocker compose exec -T gateway nginx -t
    Invoke-HotelDocker compose exec -T frontend nginx -t
    Invoke-HotelDocker compose ps
} finally { Pop-Location }

