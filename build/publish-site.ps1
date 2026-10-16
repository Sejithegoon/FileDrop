# Publishes ONLY the site/ folder to the public website repo (GitHub Pages).
# The app code stays in this private repo; the website repo receives nothing but site/.
#
# First time:  powershell -ExecutionPolicy Bypass -File build\publish-site.ps1 -RemoteUrl https://github.com/<you>/filedrop-website.git
# After that:  powershell -ExecutionPolicy Bypass -File build\publish-site.ps1
param([string]$RemoteUrl = "")
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$remotes = git remote
if ($remotes -notcontains "website") {
    if (-not $RemoteUrl) { throw "No 'website' remote yet. Run again with -RemoteUrl https://github.com/<you>/filedrop-website.git" }
    git remote add website $RemoteUrl
    Write-Host "Added remote 'website' -> $RemoteUrl"
}

if (git status --porcelain -- site) { throw "site/ has uncommitted changes. Commit them first so the published site matches the repo." }

# Build a branch whose history contains only site/ (files at its root), then push it.
git branch -D site-publish 2>$null | Out-Null
git subtree split --prefix site -b site-publish | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Could not split site/ out of the repo." }

$leaked = git ls-tree -r --name-only site-publish | Where-Object { $_ -match '^(app|console|web|tests|build|feedback_server)/' -or $_ -match '\.py$' }
if ($leaked) { git branch -D site-publish | Out-Null; throw "Refusing to publish: app files found in the website branch: $leaked" }

git push website site-publish:main
$code = $LASTEXITCODE
git branch -D site-publish | Out-Null
if ($code -ne 0) {
    Write-Warning "Push was rejected. If the website repo was created with a README or licence, delete and recreate it EMPTY (no README), then run this again."
    exit 1
}
Write-Host "Published. GitHub Pages updates within a minute or two."
