$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot

function Get-HotelDocker {
    $dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
    if ($dockerCommand) { return $dockerCommand.Source }
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA 'Programs/DockerDesktop/resources/bin/docker.exe'),
        (Join-Path $env:ProgramFiles 'Docker/Docker/resources/bin/docker.exe')
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            $env:PATH = (Split-Path -Parent $candidate) + ';' + $env:PATH
            return $candidate
        }
    }
    throw 'Docker non trovato. Installa e avvia Docker Desktop con container Linux.'
}

function Invoke-HotelDocker {
    & $script:HotelDocker @args
    if ($LASTEXITCODE -ne 0) { throw "Docker ha restituito il codice $LASTEXITCODE." }
}

$HotelDocker = Get-HotelDocker

