# Restores a backup into a NEW disposable database; never overwrites hotel data.
. (Join-Path $PSScriptRoot 'common.ps1')
Push-Location $ProjectRoot
$checkDatabase = 'hotel_restore_check_' + [Guid]::NewGuid().ToString('N').Substring(0, 12)
$created = $false
try {
    Invoke-HotelDocker compose exec -T database sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/hotel-restore-check.dump'
    Invoke-HotelDocker compose exec -T database sh -c 'createdb -U "$POSTGRES_USER" "$1"' sh $checkDatabase
    $created = $true
    Invoke-HotelDocker compose exec -T database sh -c 'pg_restore -U "$POSTGRES_USER" --exit-on-error -d "$1" /tmp/hotel-restore-check.dump' sh $checkDatabase
    Invoke-HotelDocker compose exec -T database sh -c 'psql -U "$POSTGRES_USER" -d "$1" -v ON_ERROR_STOP=1 -c "SELECT count(*) AS migrations_restored FROM django_migrations;"' sh $checkDatabase
    Write-Host 'Backup ripristinato e verificato in un database separato.'
} finally {
    try {
        if ($created -and $checkDatabase -match '^hotel_restore_check_[0-9a-f]{12}$') {
            Invoke-HotelDocker compose exec -T database sh -c 'dropdb -U "$POSTGRES_USER" "$1"' sh $checkDatabase
        }
        Invoke-HotelDocker compose exec -T database rm -f /tmp/hotel-restore-check.dump
    } finally { Pop-Location }
}
