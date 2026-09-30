# Local PostgreSQL for Windows WITHOUT Docker (portable binaries, no installer, no admin).
# Usage (from the repo root):   powershell -ExecutionPolicy Bypass -File scripts\dev-postgres.ps1
# Stop:                         .local\pgsql\bin\pg_ctl.exe -D .local\data stop
#
# Downloads PostgreSQL 16 into .local\ (gitignored) on first run, initializes a cluster,
# starts it on localhost:5432 and creates the `healtrip` role + database used by .env.example.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$local = Join-Path $root ".local"
$bin = Join-Path $local "pgsql\bin"
$data = Join-Path $local "data"
$version = "16.10-1"

New-Item -ItemType Directory -Force $local | Out-Null
if (-not (Test-Path (Join-Path $bin "pg_ctl.exe"))) {
    $zip = Join-Path $local "pg.zip"
    Write-Host "Downloading PostgreSQL $version portable binaries..."
    Invoke-WebRequest "https://get.enterprisedb.com/postgresql/postgresql-$version-windows-x64-binaries.zip" -OutFile $zip
    Expand-Archive $zip -DestinationPath $local -Force
    Remove-Item $zip
}

if (-not (Test-Path (Join-Path $data "PG_VERSION"))) {
    Write-Host "Initializing cluster (superuser: postgres / postgres - local dev only)..."
    $pw = Join-Path $local "pw.txt"
    Set-Content -Path $pw -Value "postgres" -Encoding ascii
    & (Join-Path $bin "initdb.exe") -D $data -U postgres --pwfile=$pw --auth=scram-sha-256 -E UTF8 --locale=C | Out-Null
    Remove-Item $pw
}

& (Join-Path $bin "pg_isready.exe") -h localhost -p 5432 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Starting PostgreSQL on localhost:5432..."
    Start-Process -FilePath (Join-Path $bin "pg_ctl.exe") -ArgumentList @("-D", "`"$data`"", "-l", "`"$local\pg.log`"", "start") -WindowStyle Hidden
    Start-Sleep -Seconds 4
}

$env:PGPASSWORD = "postgres"
$exists = & (Join-Path $bin "psql.exe") -h localhost -U postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='healtrip'"
if ($exists -ne "1") {
    & (Join-Path $bin "psql.exe") -h localhost -U postgres -c "CREATE ROLE healtrip LOGIN PASSWORD 'healtrip' CREATEDB;" | Out-Null
    & (Join-Path $bin "psql.exe") -h localhost -U postgres -c "CREATE DATABASE healtrip OWNER healtrip;" | Out-Null
    Write-Host "Created role/database 'healtrip'."
}
& (Join-Path $bin "pg_isready.exe") -h localhost -p 5432
