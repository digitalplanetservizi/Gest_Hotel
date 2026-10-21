. (Join-Path $PSScriptRoot 'common.ps1')
Push-Location $ProjectRoot
try {
    $backupFolder = Join-Path $ProjectRoot 'backups'
    New-Item -ItemType Directory -Path $backupFolder -Force | Out-Null
    $backupName = 'hotel-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.dump'
    Invoke-HotelDocker compose exec -T database sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/hotel-backup.dump'
    Invoke-HotelDocker compose cp database:/tmp/hotel-backup.dump (Join-Path 'backups' $backupName)
    Invoke-HotelDocker compose exec -T database rm /tmp/hotel-backup.dump
    Write-Host "Backup salvato in backups/$backupName. Copialo anche su una destinazione separata."
} finally { Pop-Location }

