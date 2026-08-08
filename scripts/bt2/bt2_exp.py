#!/usr/bin/env python3
"""Avia Solutions - BT2 experiment runner. python3 bt2_exp.py E00 E01 ..."""
import sys, statistics
import bt2_lib as B

rows = B.load_clean()
print(f"master: {len(rows)} routes | cohorts " +
      " ".join(f"{L}:{sum(1 for r in rows if r['cohort']==L)}" for L in B.COHORTS))

def floor5(r):  return r["cap5"] * r["base_mkt"] * B.STIM
def floora(r):  return r["capa"] * r["base_mkt"] * B.STIM
def dur(r):     return r["months"] / 12.0

EXPS = {
  # E00: replicate the OLD basis on the new sample = the baseline to beat.
  "E00": ("OLD basis: cap_f5 floor, capture-band uplift, annual vs annual (no duration)",
          floor5, lambda r: B.cap_band(r["cap5"])),
  "E01": ("E00 + like-for-like duration scaling (months/12)",
          lambda r: floor5(r) * dur(r), lambda r: B.cap_band(r["cap5"])),
  "E02": ("E01 but capture at ACTUAL launch frequency",
          lambda r: floora(r) * dur(r), lambda r: B.cap_band(r["capa"])),
  "E03": ("E02 + carrier type in the calibration key",
          lambda r: floora(r) * dur(r), lambda r: (B.cap_band(r["capa"]), r["typ"])),
  "E04": ("E02 + haul band in the key",
          lambda r: floora(r) * dur(r), lambda r: (B.cap_band(r["capa"]), B.haul_band(r["gcd"]))),
  "E05": ("capacity anchor: operated seats x LF, LF by carrier type x haul",
          lambda r: r["seats_ly"], lambda r: (r["typ"], B.haul_band(r["gcd"]))),
  "E06": ("capacity anchor: seats x LF, LF by type x haul x dom/int",
          lambda r: r["seats_ly"], lambda r: (r["typ"], B.haul_band(r["gcd"]), r["dom"])),
  "E07": ("geometric blend: sqrt(demand E02 x capacity E05), key type x haul",
          lambda r: (floora(r) * dur(r) * r["seats_ly"]) ** 0.5,
          lambda r: (r["typ"], B.haul_band(r["gcd"]))),
  "E08": ("seats x LF, key type x haul x legsband",
          lambda r: r["seats_ly"],
          lambda r: (r["typ"], B.haul_band(r["gcd"]), min(3, r["legs_n"] // 1500))),
  "E09": ("E08 + dom/int in key",
          lambda r: r["seats_ly"],
          lambda r: (r["typ"], B.haul_band(r["gcd"]), min(3, r["legs_n"] // 1500), r["dom"])),
  "E10": ("E08 + freqband in key",
          lambda r: r["seats_ly"],
          lambda r: (r["typ"], B.haul_band(r["gcd"]), min(3, r["legs_n"] // 1500),
                     min(2, int(r["freq"] // 5)))),
  "E11": ("seats x LF, key type x haul x legsband x capband",
          lambda r: r["seats_ly"],
          lambda r: (r["typ"], B.haul_band(r["gcd"]), min(3, r["legs_n"] // 1500),
                     B.cap_band(r["capa"]))),
}

if __name__ == "__main__":
    for eid in sys.argv[1:]:
        desc, predfn, keyfn = EXPS[eid]
        fitted, blind = B.run_experiment(rows, predfn, keyfn)
        B.log_line(eid, desc, fitted, blind, "logged")
