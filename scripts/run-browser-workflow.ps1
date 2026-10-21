# Creates and removes only its own disposable Docker project and volume.
. (Join-Path $PSScriptRoot 'common.ps1')
$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
$nodeExecutable = if ($nodeCommand) { $nodeCommand.Source } else { Join-Path $env:ProgramFiles 'nodejs/node.exe' }
if (-not (Test-Path -LiteralPath $nodeExecutable)) { throw 'Node.js e richiesto per i test browser.' }
if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot '.local/ui/node_modules/playwright'))) {
    throw 'Installa gli strumenti test: npm install --prefix .local/ui --no-save @playwright/test'
}
$testProject = 'hotel-tempio-v2-e2e'
$previousPort = $env:HTTP_PORT
$previousOrigins = $env:DJANGO_CSRF_TRUSTED_ORIGINS
$previousUrl = $env:HOTEL_E2E_URL
$createdProject = $false
Push-Location $ProjectRoot
try {
    $existing = & $HotelDocker ps -a --filter "label=com.docker.compose.project=$testProject" --format '{{.Names}}'
    if ($LASTEXITCODE -ne 0) { throw 'Docker non disponibile.' }
    if ($existing) { throw 'Esiste gia un progetto test con questo nome; non viene modificato.' }
    $existingVolume = & $HotelDocker volume ls --filter "label=com.docker.compose.project=$testProject" --format '{{.Name}}'
    if ($existingVolume) { throw 'Esiste gia un volume test con questo nome; non viene modificato.' }
    Invoke-HotelDocker tag hotel-tempio-v2-backend:latest hotel-tempio-v2-e2e-backend:latest
    Invoke-HotelDocker tag hotel-tempio-v2-frontend:latest hotel-tempio-v2-e2e-frontend:latest
    $env:HTTP_PORT = '18081'
    $env:DJANGO_CSRF_TRUSTED_ORIGINS = 'http://localhost:18081,http://127.0.0.1:18081'
    $env:HOTEL_E2E_URL = 'http://127.0.0.1:18081'
    $createdProject = $true
    Invoke-HotelDocker compose -p $testProject up -d --wait database
    Invoke-HotelDocker compose -p $testProject run --rm --no-deps backend python manage.py migrate --noinput
    Invoke-HotelDocker compose -p $testProject run --rm --no-deps backend python manage.py bootstrap
    Invoke-HotelDocker compose -p $testProject up -d --wait --no-build
    & $nodeExecutable (Join-Path $PSScriptRoot 'browser-workflow.cjs')
    if ($LASTEXITCODE -ne 0) { throw 'Il test browser del flusso gestionale non e riuscito.' }
} finally {
    try {
        if ($createdProject) { Invoke-HotelDocker compose -p $testProject down --volumes }
    } finally {
        $env:HTTP_PORT = $previousPort
        $env:DJANGO_CSRF_TRUSTED_ORIGINS = $previousOrigins
        $env:HOTEL_E2E_URL = $previousUrl
        Pop-Location
    }
}
