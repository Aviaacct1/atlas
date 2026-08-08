# scripts/bt2: the BT2 evidence programme

The route-level back-test that produces the airport track record and the promoted model
`data/bt2_model_v1_2.pkl`. These scripts train and score; the engine only scores.

Author: Avia Solutions. 8 August 2026.

## Where the pieces live, and why they are not all here

| File | Location | Reason |
|---|---|---|
| `bt2_model.py` | `scripts/` | `scripts/bt2_features.py` imports it as `bt2_model`, with `scripts/` on the import path, so that copy is the live one. It arrived here as well on 8 August and the duplicate was removed before the first commit. One owner. |
| `bt2_features.py` | `scripts/` | Imported by `scripts/run_qsi_bum.py` as `bt2_features`, from `scripts/`. Same reason. |
| everything else | here | Training, discovery and the evidence log. Nothing the live forecast imports. |

## Paths

Every location resolves through `avia_forecast/paths.py`. Until 8 August 2026 these
twelve scripts hard-coded `/sessions/wizardly-peaceful-tesla/mnt/...` as the only value,
not as a fallback, on 23 lines. That is a Cowork session name, and the session had ended,
so none of them could run on any machine. The model behind the published track record
could be used and could not be reproduced.

The data they read stays in the store root, `C:\Avia\bt2`: the base strength files, the
quarterly DB1B and coupon extracts, the airport track record and the experiment log.
Data never enters the repository. `bt2_experiments.log` is the exception and is tracked
deliberately, because it is the record of what was tried and what it scored.

## Before trusting a result from these

Two questions from the Meridian migration note apply here directly. What was every
adjustment fitted against, and does the published accuracy describe the thing the client
is shown. `webapp/dashboard.html` displays a track record; nothing the live forecast
imports produces it. Settle that before the Global Forecast is sold.
