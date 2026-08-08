<#
    Atlas: bring the Global Forecast under version control and move it to C:\src\atlas.
    Avia Solutions. Version 1.0, 8 August 2026.

    Run this in YOUR PowerShell, on the Dev PC, from C:\Avia\avia_forecast_build.
    Git through a Cowork file mount corrupts .git/index, which is why this is a script
    you run rather than something a session did.

        cd C:\Avia\avia_forecast_build
        powershell -ExecutionPolicy Bypass -File .\migrate_to_atlas.ps1
        powershell -ExecutionPolicy Bypass -File .\migrate_to_atlas.ps1 -Go

    The Bypass applies to that one invocation and changes nothing on the machine. Your
    execution policy blocks unsigned scripts, which is the correct default and worth
    keeping. If you would rather set it once for your own account instead:

        Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

    It stops at the first failure and tells you what to do. Nothing here rewrites
    history: no rebase, no force push, no filter-branch, no hard reset. Steps 1 to 5
    are recoverable from the remote once step 5 has run.

    -SkipTests   skip the suite, only if you have just run it yourself
    -Resume <n>  start at step n, for a re-run after fixing something
#>
[CmdletBinding()]
param(
    [switch]$Go,
    [switch]$SkipTests,
    [int]$Resume = 1
)

$ErrorActionPreference = "Stop"
$repo   = "C:\Avia\avia_forecast_build"
$target = "C:\src\atlas"
$tag    = "atlas-baseline-08Aug2026"
$script:step = 0

function Say([string]$m, [string]$c = "Gray") { Write-Host $m -ForegroundColor $c }
function Head([string]$m) { $script:step++; Say ""; Say ("=" * 72); Say ("STEP $($script:step). $m") "Cyan"; Say ("=" * 72) }
function Skip { return ($script:step -lt $Resume) }
function Die([string]$m) { Say ""; Say "STOPPED: $m" "Red"; exit 1 }
function Run([string]$what, [scriptblock]$block) {
    if (-not $Go) { Say "  would run: $what" "DarkGray"; return }
    Say "  $what" "White"
    # Reset before invoking. A cmdlet such as Move-Item does not set $LASTEXITCODE, so a
    # stale non-zero left by an earlier git call would read as this step failing.
    $global:LASTEXITCODE = 0
    & $block
    if ($LASTEXITCODE -ne 0) { Die "$what returned exit code $LASTEXITCODE" }
}

if (-not $Go) {
    Say ""
    Say "DRY RUN. Checks run for real; nothing is changed. Add -Go to commit, push and move." "Yellow"
}

# ---------------------------------------------------------------------------
Head "Confirm the starting state"
if (-not (Skip)) {
    if (-not (Test-Path (Join-Path $repo ".git"))) { Die "$repo is not a git repository." }
    Set-Location $repo

    # A stale .git/index.lock. Git leaves one behind when it cannot unlink the file,
    # which is what happens when a git command runs against this folder through a Cowork
    # session mount: the mount blocks unlink. Even a --dry-run takes the lock. A zero
    # byte lock with a readable index means nothing was written and the lock is simply
    # litter; anything else is a real interrupted write and is not for a script to clear.
    $lock = Join-Path $repo ".git\index.lock"
    if (Test-Path $lock) {
        $running = @(Get-Process git -ErrorAction SilentlyContinue)
        if ($running.Count -gt 0) { Die "another git process is running. Let it finish, then run this again." }
        $size = (Get-Item $lock).Length
        git ls-files > $null 2>&1
        $indexOk = ($LASTEXITCODE -eq 0)
        Say "  stale .git\index.lock found: $size bytes, index readable: $indexOk" "Yellow"
        if ($size -ne 0 -or -not $indexOk) {
            Say "  the lock is not empty or the index will not read, so a write was interrupted." "Red"
            Say "  Recover by hand: delete .git\index.lock, then 'git reset -q' to rebuild the" "Red"
            Say "  index from HEAD. That leaves the working tree alone." "Red"
            Die "not clearing this automatically."
        }
        Run "remove the stale lock" { Remove-Item $lock -Force }
        if (-not $Go) { Say "  dry run: delete it by hand first, or it will stop step 3 again" "Yellow" }
    }

    $commits = (git rev-list --count HEAD)
    $branch  = (git rev-parse --abbrev-ref HEAD)
    $remotes = (git remote)
    Say "  repository : $repo"
    Say "  commits    : $commits   branch: $branch   remotes: $(if ($remotes) { $remotes } else { 'none' })"

    if (-not $SkipTests) {
        Say "  running the suite, circa 30 seconds"
        py -3.12 -m pytest tests -q
        if ($LASTEXITCODE -ne 0) { Die "the test suite failed. Do not commit a red tree." }
        Say "  suite green" "Green"
    }
    py -3.12 scripts\validate_repo.py
    if ($LASTEXITCODE -ne 0) { Die "the repository check failed. The pre-commit hook would block the commit anyway." }
    Say "  repository check passed" "Green"

    # One duplicate to clear before the first commit. bt2_model.py arrived twice: once
    # at scripts\ (the copy scripts\bt2_features.py imports, so the live one) and once
    # at scripts\bt2\ with the rest of the training family. They are byte-identical
    # today, which is exactly when a duplicate is cheapest to remove and hardest to
    # notice. The session that prepared this tree could not delete through its mount.
    $dupe = Join-Path $repo "scripts\bt2\bt2_model.py"
    $live = Join-Path $repo "scripts\bt2_model.py"
    if ((Test-Path $dupe) -and (Test-Path $live)) {
        $a = (Get-FileHash $dupe).Hash; $b = (Get-FileHash $live).Hash
        if ($a -ne $b) { Die "scripts\bt2\bt2_model.py and scripts\bt2_model.py differ. Read both before removing either." }
        Run "remove the duplicate scripts\bt2\bt2_model.py" { Remove-Item $dupe }
    }
}

# ---------------------------------------------------------------------------
Head "Untrack anything already in git that the ignore rules now exclude"
if (-not (Skip)) {
    Set-Location $repo
    # .gitignore does not untrack a file that is already tracked, so a generated file
    # committed before the rules tightened stays in every future commit and travels to
    # the workstation in the clone. Git can name them exactly, which is better than a
    # list somebody has to maintain.
    $stale = @(git ls-files -i -c --exclude-standard)
    if ($stale.Count -eq 0) {
        Say "  nothing tracked is excluded by the ignore rules" "Green"
    } else {
        Say "  tracked but now excluded, so they will be untracked (the files stay on disk):"
        $stale | ForEach-Object { Say "    $_" "Yellow" }
        foreach ($s in $stale) {
            $f = $s
            Run "git rm --cached $f" { git rm --cached --quiet -- $f }
        }
    }
}

# ---------------------------------------------------------------------------
Head "Simulate the staging list and read it"
if (-not (Skip)) {
    Set-Location $repo
    $staged = @(git add -A -n) 2>$null
    # Deliberately specific. An earlier version matched "access_password", which caught
    # webapp/TEAM_ACCESS_password.md (documentation about the mechanism, not the secret),
    # and "backup_pre", which caught the attic copy of the pre-Observatory dashboard.
    # Both belong in the commit. Only access_password.txt is the secret, and only the
    # backup FOLDERS are generated output.
    $pattern = "\.duckdb|\.err\.log|access_password\.txt|/venv/|\.venv/|_dt_cache|oag_serve|\.pptx|\.pdf|\.bak-|backup_pre[a-z_]*[0-9_]*/|webapp/data/.*\.json|/\.pytest_cache/"
    $forbidden = $staged | Select-String -Pattern $pattern
    $bad = $forbidden | Where-Object { $_ -notmatch "bt2_experiments\.log" }
    if ($bad) {
        Say "  these would be committed and should not be:" "Red"
        $bad | ForEach-Object { Say "    $_" "Red" }
        Die "fix .gitignore, then run this again."
    }
    Say "  nothing forbidden would stage" "Green"
    Say "  files that would be added: $($staged.Count)"
}

# ---------------------------------------------------------------------------
Head "Baseline commit and tag"
if (-not (Skip)) {
    Set-Location $repo
    $msg = @"
Baseline 8 Aug 2026: the tree under version control

Brings in 22 engine modules and 33 test modules that had never been committed:
the capacity layer, the configured-airport work behind Zagreb and Bristol, the
shock resilience module, the Observatory output modules and the OAG ingest.

Corrections in this commit, each verified against the filesystem:
- global_demand rebound the DATA name from paths to the repo's own data folder,
  so estimated_bG_by_country, oef_gdp_pop_by_iso2 and aci_hub_calibration_2024
  were looked for inside the repository, were not there, and each load returned
  an empty dictionary. 137 country elasticities, 197 country GDP forecasts and
  2,430 airport connecting shares now reach the engine. This MOVES THE NUMBERS:
  world 2060 O&D departing pax 10,983m to 9,644m, CAGR 3.64% to 3.26%.
- six data loads now name the file, the path and what is lost, and stop.
  AVIA_ALLOW_MISSING_DATA=1 permits a deliberate degraded run and records it.
- eleven environment variable names for five data locations reduced to six, all
  read only by avia_forecast/paths.py.
- test_parity_harness addressed the pilot workbook two folders above the repo and
  had skipped since it was written. It runs: 332 passed, 0 skipped.
- peakhour_workbook_addsheet.py recovered from the project tree. It produced the
  delivered 4 August peak-hour workbook and existed in one place on the estate.
- 17 data-operations scripts repointed off a dead Cowork session path and brought
  in under scripts/dataops and scripts/bt2.
"@
    Run "git add -A" { git add -A }
    Run "git commit" { git commit -m $msg }
    Run "git tag $tag" { git tag $tag }
    if ($Go) { Say "  tagged $tag" "Green" }
}

# ---------------------------------------------------------------------------
Head "Rename the branch to main, as Meridian"
if (-not (Skip)) {
    Set-Location $repo
    if ((git rev-parse --abbrev-ref HEAD) -eq "master") {
        Run "git branch -m master main" { git branch -m master main }
    } else {
        Say "  already on $(git rev-parse --abbrev-ref HEAD), nothing to do"
    }
}

# ---------------------------------------------------------------------------
Head "Add the remote and push"
if (-not (Skip)) {
    Set-Location $repo
    # The account name is read from the Meridian clone rather than typed, so this
    # cannot pick up a placeholder or the wrong case.
    $mUrl = (git -C C:\src\meridian remote get-url origin)
    if (-not $mUrl) { Die "cannot read the Meridian remote; is C:\src\meridian a clone?" }
    $owner = [regex]::Match($mUrl, 'github\.com[:/]([^/]+)/').Groups[1].Value
    if (-not $owner) { Die "cannot read the account name out of $mUrl" }
    $url = "https://github.com/$owner/atlas.git"
    Say "  remote will be: $url"

    if ((git remote) -contains "origin") {
        $cur = (git remote get-url origin)
        if ($cur -ne $url) { Die "origin already points at $cur. Resolve that by hand." }
        Say "  origin already set correctly"
    } else {
        Run "git remote add origin $url" { git remote add origin $url }
    }
    Run "git push -u origin main" { git push -u origin main }
    Run "git push origin --tags" { git push origin --tags }
    if ($Go) {
        $ahead = (git rev-list --count "origin/main..HEAD")
        if ($ahead -ne "0") { Die "the push did not land: $ahead commit(s) still local." }
        Say "  pushed, and the remote matches local" "Green"
    }
}

# ---------------------------------------------------------------------------
Head "Move the working tree to C:\src\atlas"
if (-not (Skip)) {
    Set-Location $repo
    if (Test-Path $target) { Die "$target already exists. Move it aside first." }
    $dirty = (git status --porcelain)
    if ($dirty) { Die "the tree is not clean; commit or stash before moving." }
    Set-Location C:\
    Run "Move-Item $repo $target" { Move-Item $repo $target }
    if ($Go) {
        Set-Location $target
        Say "  now at: $target, HEAD $(git log --oneline -1)" "Green"
    }
}

# ---------------------------------------------------------------------------
Head "Virtual environment, dependencies and the host check"
if (-not (Skip)) {
    if ($Go) { Set-Location $target }
    Run "py -3.12 -m venv .venv" { py -3.12 -m venv .venv }
    # Call the venv interpreter by path. py -3.12 selects the SYSTEM 3.12 whether or
    # not a venv is active, so Activate-then-py installs outside the environment.
    Run "pip install -r requirements.txt" { .\.venv\Scripts\python.exe -m pip install -q -r requirements.txt }
    Run "pip install -r requirements-dev.txt" { .\.venv\Scripts\python.exe -m pip install -q -r requirements-dev.txt }
    if ($Go) {
        .\.venv\Scripts\python.exe check_env.py
        if ($LASTEXITCODE -ne 0) { Die "check_env.py says this host is not ready. Fix what it named, then -Resume 7." }
        Say "  host ready" "Green"
    }
}

# ---------------------------------------------------------------------------
Head "Repoint at the Meridian clone and move preagg to the store root"
if (-not (Skip)) {
    $old = "C:\Users\Carte\OneDrive\Documents\Claude\Projects\Avia QSI Tool\app\preagg.duckdb"
    $new = "C:\Avia\preagg.duckdb"
    Run "set AVIA_QSI_APP for your user" {
        [Environment]::SetEnvironmentVariable("AVIA_QSI_APP", "C:\src\meridian\app", "User")
    }
    if (Test-Path $new) {
        Say "  $new already in place"
    } elseif (Test-Path $old) {
        Run "move preagg.duckdb to the store root" { Move-Item $old $new }
    } else {
        Say "  preagg.duckdb is at neither location; check before running the QSI path" "Yellow"
    }
    Say "  paths.py resolves PREAGG from the store root first and the application folder second,"
    Say "  so this works before and after the move."
}

# ---------------------------------------------------------------------------
Head "Re-capture the golden baseline"
if (-not (Skip)) {
    if ($Go) {
        Set-Location $target
        .\.venv\Scripts\python.exe scripts\golden_baseline.py capture
        if ($LASTEXITCODE -ne 0) { Die "the golden capture named a missing root. Set AVIA_DB_ROOT to C:\Avia and re-run with -Resume 9." }
        git add data\golden_manifest_*.json
        git commit -m "Golden baseline re-captured after the move to C:\src\atlas. Every key is prefixed with the top folder name, so the rename from avia_forecast_build changes every key: that is the rename, not corruption."
        git push
        Say "  captured, committed and pushed" "Green"
    } else {
        Say "  would capture, commit and push a fresh golden manifest"
    }
}

# ---------------------------------------------------------------------------
Head "Set the superseded originals aside"
if (-not (Skip)) {
    # The 17 data-operations scripts now live in the repo, repointed. The copies at
    # C:\Avia are superseded and must not become a second owner. They are moved, not
    # deleted: a deletion is a loss.
    $attic = "C:\Avia\_superseded_08Aug2026"
    if ($Go) { New-Item -ItemType Directory -Force -Path $attic | Out-Null }
    $roots = @("back_test.py","back_test_cohort.py","back_test_v2.py","goa_qsi_test.py","qsi_market.py",
               "check_oag_truncation.py","check_oag_weeks.py","comparator_extract.py","dedupe_oag_periods.py",
               "genoa_extract.py","goa_nyc_forecast.py","ingest_all_oag.py","ingest_all_years.py","oag_ingest.py",
               "reingest_multisheet.py","run_forecast.py","run_multihub_qsi.py","sabre_2023_control.py",
               "sabre_cabin_diff.py","sabre_carrier_diff.py","sabre_check_2025.py","sabre_compare_analyst.py",
               "sabre_compare_exact.py","sabre_compare_refined.py","sabre_direction_check.py",
               "sabre_factor_check.py","sabre_generate_demand.py","sabre_generate_extract.py","sabre_ingest.py",
               "sabre_query_lhrsjc.py","validate_oag_store.py")
    foreach ($f in $roots) {
        $p = Join-Path "C:\Avia" $f
        if (Test-Path $p) { Run "move $f aside" { Move-Item $p (Join-Path $attic $f) -Force } }
    }
    if (Test-Path "C:\Avia\bt2") {
        # the .py move aside; the data, models and the experiment log STAY, because the
        # repo copies read them from here through paths.py
        if ($Go) { New-Item -ItemType Directory -Force -Path (Join-Path $attic "bt2") | Out-Null }
        # Captured into plain variables first: $_ is bound by ForEach-Object in its own
        # scope and would not resolve inside the scriptblock Run invokes.
        foreach ($py in @(Get-ChildItem "C:\Avia\bt2\*.py")) {
            $src = $py.FullName
            $dst = Join-Path (Join-Path $attic "bt2") $py.Name
            Run "move bt2\$($py.Name) aside" { Move-Item $src $dst -Force }
        }
    }
    Say "  originals are in $attic, not deleted. Remove them once you are happy." "Green"
}

# ---------------------------------------------------------------------------
Head "Final proof: the clone runs"
if (-not (Skip) -and $Go) {
    $proof = "C:\src\_atlas_clone_proof"
    if (Test-Path $proof) { Remove-Item -Recurse -Force $proof }
    $url = (git -C $target remote get-url origin)
    git clone $url $proof
    if ($LASTEXITCODE -ne 0) { Die "the clone failed." }
    Set-Location $proof
    py -3.12 -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -q -r requirements.txt
    .\.venv\Scripts\python.exe check_env.py
    $rc = $LASTEXITCODE
    Set-Location $target
    if ($rc -ne 0) {
        Say "  the clone does NOT stand up on its own. check_env named what is missing above." "Red"
        Say "  That is the point of this step: a clone contains exactly what is tracked, so" "Red"
        Say "  whatever it lacks is either data (correct) or something that should be committed." "Red"
        Die "resolve it before trusting the repository."
    }
    Say "  a fresh clone provisions and passes check_env" "Green"
    Say "  proof clone left at $proof; delete it when you are satisfied." "DarkGray"
}

Say ""
Say ("=" * 72) "Green"
if ($Go) {
    Say "Done. atlas is on GitHub with its history and tag, running from C:\src\atlas." "Green"
    Say "Read CAPABILITY_AUDIT.md and SWITCH_REGISTER.md next: what is built and off." "Green"
} else {
    Say "Dry run complete and nothing failed. Run again with -Go." "Green"
}
Say ("=" * 72) "Green"
