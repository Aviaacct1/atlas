r"""Central data-root resolver. Author: Avia Solutions.

Every data location the engine, the webapp and the build scripts read resolves through
here, so the code runs on any machine and provisioning a host changes variables rather
than code. Resolution order per location:

  1. the environment variable named below (set these on a workstation, a server or CI);
  2. the Windows working location;
  3. the Cowork sandbox mount, discovered by glob, never by a session name. A literal
     /sessions/<name>/ path is dead the moment that session ends, which is why
     scripts/validate_repo.py blocks one anywhere in the tree and exempts this file.

The first candidate that exists wins. If none exists, the first is returned, so a fresh
machine points at the intended location and check_env.py reports what is missing.

FIVE variables, one per location. Nothing else in the tree may read a data path from the
environment or write one as a literal.

    AVIA_GLOBAL_ROOT   the Global folder            default E:\Avia\Global
    AVIA_DB_ROOT       the store root               default C:\Avia
    AVIA_QSI_APP       the Meridian application     default C:\src\meridian\app
    AVIA_ZAGREB        the Zagreb engagement folder default E:\Avia\Zagreb
    AVIA_DUCKDB_TMP    duckdb scratch               unset, duckdb chooses

Superseded on 8 August 2026, and removed from the modules that read them: QSI_APP,
QSI_OAG, QSI_SABRE, AVIA_OAG, AVIA_OAG_DB, AVIA_OAG_STORE. Eleven names addressed five
locations, the OAG store answered to three of them, and webapp/qsi_service.py and this
file each carried their own default for the Meridian folder, so setting one and not the
other gave a host with half the tool pointing at the old location. They are read here for
one release as fallbacks, so a machine part-way through the move still resolves, and
_legacy_env() reports each one it uses.
"""
import glob
import os
import sys

_LEGACY_USED: list[str] = []


def _first(cands):
    for c in cands:
        if c and os.path.exists(c):
            return c
    return cands[0]


def _mnt(sub):
    """Discover a Cowork sandbox mount without hard-coding the (per-session) mount name."""
    hits = glob.glob("/sessions/*/mnt/" + sub)
    return hits[0] if hits else None


def _legacy_env(*names):
    """Read a superseded variable, and say so. Silence here is how a host ends up half
    pointed at the old location with nothing to show for it."""
    for n in names:
        v = os.environ.get(n)
        if v:
            _LEGACY_USED.append(n)
            print(f"paths: {n} is superseded and was used. Set the current variable "
                  f"instead and unset {n}. See the header of avia_forecast/paths.py.",
                  file=sys.stderr)
            return v
    return None


# --- the five locations ------------------------------------------------------
GLOBAL = (os.environ.get("AVIA_GLOBAL_ROOT")
          or _first([r"E:\Avia\Global", _mnt("Global"), _mnt("E:--Avia/Global")]))

AVIA = (os.environ.get("AVIA_DB_ROOT")
        or _legacy_env("AVIA_OAG_DB", "AVIA_OAG_STORE", "QSI_OAG", "QSI_SABRE")
        or _first([r"C:\Avia", _mnt("Avia")]))
if os.path.isfile(AVIA):                     # a legacy variable named the store, not the root
    AVIA = os.path.dirname(AVIA)

QSI_APP = (os.environ.get("AVIA_QSI_APP")
           or _legacy_env("QSI_APP")
           or _first([
               r"C:\src\meridian\app",       # the clone with the history and the remote
               r"C:\Users\Carte\OneDrive\Documents\Claude\Projects\Avia QSI Tool\app",
               _mnt("src/meridian/app"),
               _mnt("Avia QSI Tool/app"),
           ]))

ZAGREB = (os.environ.get("AVIA_ZAGREB")
          or _first([r"E:\Avia\Zagreb", _mnt("Zagreb"), _mnt("E:--Avia/Zagreb")]))

# Documents, not data: the shared project folder that holds the deliverables and Jess
# Rowden's pilot workbook. Named here because three modules were resolving it their own
# way, and tests/test_parity_harness.py was looking two folders above the repository,
# which is C:\Avia today and C:\src after the move, and is the workbook's location in
# neither. It has been skipping since it was written.
PROJECT_DIR = (os.environ.get("AVIA_PROJECT_DIR")
               or _first([
                   r"C:\Users\Carte\OneDrive\Documents\Claude\Projects\Avia Global Forecast Tool",
                   _mnt("Avia Global Forecast Tool"),
               ]))
PILOT_WORKBOOK = os.path.join(PROJECT_DIR, "01 Pax Forecast Top Down (JR) - Avia additions v0.1.xlsx")

DUCKDB_TMP = os.environ.get("AVIA_DUCKDB_TMP") or None

# Egnyte, mapped to Z: on the Dev PC. Source files only: the Sabre ODPOO and OAG pulls
# the ingest scripts read. No tool code and no store ever lives here.
EGNYTE = (os.environ.get("AVIA_EGNYTE")
          or _first([r"Z:\Shared\Company Data", _mnt("Shared/Company Data")]))
SABRE_SRC = os.path.join(EGNYTE, "18 Products", "Data", "Sabre", "ODPOO")
OAG_SRC = os.path.join(EGNYTE, "18 Products", "Data", "OAG")

# US DOT source files (DB1B, coupon, T100), used by the BT2 evidence programme.
US_MARKET = (os.environ.get("AVIA_US_MARKET")
             or _first([r"E:\Avia\Usmarket data", r"C:\Avia\US Market Data",
                        _mnt("Usmarket data"), _mnt("E:--Avia/Usmarket data"),
                        _mnt("Avia/US Market Data")]))

# --- everything derived ------------------------------------------------------
DATA = os.path.join(GLOBAL, "data")
OEF_DIR = os.path.join(GLOBAL, "OEF")
ACI_DIR = os.path.join(GLOBAL, "ACI")
ACI_DECRYPT = os.path.join(DATA, "aci_decrypted")
SABRE_DB = os.path.join(AVIA, "sabre.duckdb")
OAG_DB = os.path.join(AVIA, "oag.duckdb")
QSI_REF = os.path.join(QSI_APP, "reference_tables", "airport_city_country.csv")
OEF_GDP_XLSX = os.path.join(OEF_DIR, "OEF GDP Forecast 31Jul2024 - GDP per CAP added (AR 08Oct2024).xlsx")

# preagg is data, so it resolves from the store root. It sat in the Meridian application
# folder until 8 August 2026, which meant repointing AVIA_QSI_APP at the Meridian clone
# broke it, because a clone holds code and never data. The old location stays as a second
# candidate so a machine part-way through the move still resolves.
PREAGG = _first([
    os.path.join(AVIA, "preagg.duckdb"),
    os.path.join(QSI_APP, "preagg.duckdb"),
])


def serve_copy(pattern="oag_serve_*.duckdb"):
    """Newest serve copy of a store in the store root, or None. The serve copies are
    written by the ingest and are never committed."""
    hits = sorted(glob.glob(os.path.join(AVIA, pattern)))
    return hits[-1] if hits else None


def report() -> dict:
    """Every resolved location, for check_env.py and for a run to stamp on its output."""
    return {"GLOBAL": GLOBAL, "AVIA": AVIA, "QSI_APP": QSI_APP, "ZAGREB": ZAGREB,
            "PROJECT_DIR": PROJECT_DIR, "DATA": DATA, "SABRE_DB": SABRE_DB,
            "OAG_DB": OAG_DB, "PREAGG": PREAGG, "PILOT_WORKBOOK": PILOT_WORKBOOK,
            "DUCKDB_TMP": DUCKDB_TMP, "legacy_variables_used": sorted(set(_LEGACY_USED))}
