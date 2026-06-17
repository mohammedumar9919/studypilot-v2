# Run the Postgres ingest worker (SP-013a)
param(
    [switch]$Once
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..\apps\api

if (-not $env:DATABASE_URL) {
    $env:DATABASE_URL = "postgresql+psycopg://studypilot:studypilot@localhost:5433/studypilot"
}

$args = @("-m", "app.cli.run_ingest_worker")
if ($Once) { $args += "--once" }

python @args
