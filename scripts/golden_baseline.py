"""Golden baseline for the Git migration (CHANGELOG 98).

capture: hash (sha256) + size every artefact that migrates - engine repo code, data
extracts, webapp pages and data, models, bt2 evidence, C:\\Avia root scripts - plus
semantic counts (JSON keys, airport counts, CSV rows) so intentional regeneration can
be told apart from corruption. Writes data/golden_manifest_<date>.json.

verify: re-hash against a manifest and report IDENTICAL / CHANGED / MISSING / NEW.
Run verify on the machine after each migration step; the tag is applied only on a
clean report. Excludes: *.duckdb, serve copies, logs, __pycache__, .git.

Usage:  python scripts/golden_baseline.py capture
        python scripts/golden_baseline.py verify data/golden_manifest_2026-08-07.json
Author: Avia Solutions."""
import csv, datetime, hashlib, json, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from avia_forecast.paths import AVIA   # the data root, resolved centrally

# AVIA was the repo's parent folder until 8 August 2026, which held only while the repo
# lived at C:\Avia\avia_forecast_build. Moving the repo to C:\src\atlas made the parent
# C:\src, where bt2 and the loose root scripts are not, and walk() would have returned
# nothing for them without saying so. The data root is now resolved, never inferred from
# where the code happens to sit.

ROOTS = [
    (REPO, ("avia_forecast", "scripts", "webapp", "githooks", "config", "data")),
    (AVIA, ("bt2",)),
]
ROOT_FILES_GLOB = [".py"]   # loose scripts at C:\Avia root
EXCLUDE_EXT = {".duckdb", ".log", ".pyc", ".tmp"}
EXCLUDE_SUBSTR = ("oag_serve_", "__pycache__", ".git", "err.log", "golden_manifest",
                  ".bak-",     # editor backup snapshots are machine-local clutter, not artefacts
                  ".pytest_tmp", ".venv")

# The first cross-machine verify (23 August 2026) reported every source file CHANGED:
# the dev PC checks out CRLF (Windows autocrlf) and the workstation clone keeps LF, so
# identical git content hashed differently on disk. Text files are therefore hashed with
# newlines normalised, so the manifest states content, not checkout convention. Binary
# and data extensions are hashed as bytes, exactly as before.
TEXT_EXT = {".py", ".md", ".yaml", ".yml", ".html", ".css", ".js", ".txt", ".csv",
            ".json", ".sql", ".ps1", ".bat", ".cfg", ".toml", ".in"}

def eligible(path):
    if any(s in path for s in EXCLUDE_SUBSTR):
        return False
    return os.path.splitext(path)[1].lower() not in EXCLUDE_EXT

def _is_text(path):
    # extensionless files under githooks are shell text (the pre-commit hook was the one
    # line-ending straggler in the 23 August cross-machine verify)
    if os.sep + "githooks" + os.sep in path or "/githooks/" in path:
        return True
    return os.path.splitext(path)[1].lower() in TEXT_EXT


def sha(path, h=None):
    h = hashlib.sha256()
    if _is_text(path):
        with open(path, "rb") as f:
            h.update(f.read().replace(b"\r\n", b"\n"))
        return h.hexdigest()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def semantic(path):
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".json":
            d = json.load(open(path, encoding="utf-8"))
            if isinstance(d, dict):
                s = {"type": "dict", "keys": len(d)}
                for k in ("airports", "years", "flows"):
                    if k in d and hasattr(d[k], "__len__"):
                        s[f"n_{k}"] = len(d[k])
                return s
            return {"type": "list", "n": len(d)}
        if ext in (".csv", ".tsv"):
            with open(path, encoding="utf-8", errors="replace") as f:
                return {"rows": sum(1 for _ in f) - 1}
    except Exception as e:
        return {"parse_error": str(e)[:80]}
    return None

def walk():
    files = []
    missing = [os.path.join(r, s) for r, subs in ROOTS for s in subs
               if not os.path.isdir(os.path.join(r, s))]
    if missing:
        print("golden baseline: these named roots are not present, so nothing was hashed "
              "from them. A manifest captured now would be incomplete:")
        for m in missing:
            print("  - " + m)
        print("  data root in use: " + AVIA + "  (set AVIA_DB_ROOT to change it)")
        sys.exit(1)
    for root, subs in ROOTS:
        for sub in subs:
            base = os.path.join(root, sub)
            if not os.path.isdir(base):
                continue
            for dp, dns, fns in os.walk(base):
                dns[:] = [d for d in dns if not any(s in d for s in EXCLUDE_SUBSTR)]
                for fn in fns:
                    p = os.path.join(dp, fn)
                    if eligible(p):
                        files.append(p)
    for fn in os.listdir(AVIA):
        p = os.path.join(AVIA, fn)
        if os.path.isfile(p) and os.path.splitext(fn)[1] in ROOT_FILES_GLOB and eligible(p):
            files.append(p)
    return sorted(files)

def rel(p):
    for root, _ in ROOTS:
        if p.startswith(root + os.sep):
            return os.path.basename(root) + "/" + os.path.relpath(p, root).replace(os.sep, "/")
    return p

def capture():
    files = walk()
    man = {"captured": datetime.date.today().isoformat(),
           "purpose": "pre-Git-migration golden baseline; verify after every move",
           "n_files": len(files), "files": {}}
    tot = 0
    for p in files:
        st = os.stat(p)
        e = {"sha256": sha(p), "bytes": st.st_size}
        sem = semantic(p)
        if sem:
            e["semantic"] = sem
        man["files"][rel(p)] = e
        tot += st.st_size
    outp = os.path.join(REPO, "data", f"golden_manifest_{man['captured']}.json")
    json.dump(man, open(outp, "w", encoding="utf-8"), indent=1, sort_keys=True)
    print(f"captured {len(files)} files, {tot/1e6:.1f} MB -> {outp}")

def verify(manifest_path):
    man = json.load(open(manifest_path, encoding="utf-8"))
    now = {rel(p): p for p in walk()}
    ident = changed = 0
    missing = [k for k in man["files"] if k not in now]
    new = [k for k in now if k not in man["files"]]
    diffs = []
    for k, e in man["files"].items():
        if k in now:
            h = sha(now[k])
            if h == e["sha256"]:
                ident += 1
            else:
                changed += 1
                diffs.append(k)
    print(f"IDENTICAL {ident} | CHANGED {changed} | MISSING {len(missing)} | NEW {len(new)}")
    for k in diffs[:40]: print("  changed:", k)
    for k in missing[:40]: print("  MISSING:", k)
    for k in new[:20]: print("  new:", k)
    if not missing and not changed:
        print("CLEAN - safe to tag")
    elif missing:
        print("DO NOT TAG - files missing against the baseline")
    else:
        print("Changed files present - confirm each is an intended regeneration before tagging")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        verify(sys.argv[2])
    else:
        capture()
