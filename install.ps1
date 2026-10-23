$repo = $PSScriptRoot
$skills = Join-Path $env:USERPROFILE ".claude\skills"
New-Item -ItemType Directory -Force $skills | Out-Null

Get-ChildItem $skills -Attributes ReparsePoint | Where-Object { $_.Name -like "jb*" } | ForEach-Object { $_.Delete() }
Get-ChildItem (Join-Path $repo "skills") -Directory -Filter "jb*" | ForEach-Object {
    New-Item -ItemType Junction -Path (Join-Path $skills $_.Name) -Target $_.FullName | Out-Null
    Write-Output "Skill installed: $($_.Name)"
}

$config = Join-Path $repo "config.toml"
if (-not (Test-Path $config)) {
    Copy-Item (Join-Path $repo "config.example.toml") $config
    Write-Output "config.toml created from config.example.toml, to fill in."
}

python -m pip install --user --quiet mutagen pillow
Write-Output "mutagen and Pillow installed."
