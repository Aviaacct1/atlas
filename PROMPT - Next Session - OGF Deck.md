# Kickoff prompt for the next session

Copy everything below the line into a new chat.

---

We are building the Observatory Global Aviation Forecast deck, in the shape of Boeing's
"Market Overview" consultant deck, on Avia's own forecast and assumptions. Two purposes:
the team (Stefan, Jess, Nick, Jol) uses it to review and challenge the forecast, and we
use it with third parties. Building it is also the diagnostic: every slide we cannot fill
is a gap in the forecast, not a formatting problem.

**Mount these folders:** `C:\src\atlas`, `C:\Avia`, `E:\Avia`,
`C:\Users\Carte\OneDrive\Documents\Claude\Projects\Avia Global Forecast Tool`.

**Read first, in this order:**

1. `C:\src\atlas\HANDOVER - OGF Deck Build - 9 August 2026.md`, the full state.
2. `C:\src\atlas\OGF DECK - Slide Inventory against Boeing Market Overview 2025.md`, all
   22 content slides mapped: 6 we can produce, 7 partial, 9 we cannot.
3. `C:\src\atlas\MEASUREMENTS.md`, the numbers behind the open decisions.
4. `C:\src\atlas\SWITCH_REGISTER.md` and `CAPABILITY_AUDIT.md`, what is switched off and
   what nothing calls.

**Confirm the tree is where the handover says before doing anything else:**

    cd C:\src\atlas
    py -3.12 -m pytest tests -q                      expect 336 passed
    py -3.12 scripts\validate_repo.py                expect exit 0
    py -3.12 scripts\compare_regions_boeing.py       expect world Avia 3.3% v Boeing 4.2%

If any of those differs, stop and find out why before building anything.

**Hard rules.**

- Git commands run in my PowerShell, never through the session's file mount. A mount
  blocks unlink, so even `git add --dry-run` leaves a stale `.git\index.lock`. You write
  code and run tests; I commit. Pull before editing, push after.
- Every figure names its source in the same sentence: a file read this session, an Egnyte
  file, a URL searched this session, or the locked model. Nothing from recall. If there is
  no source, say so and ask.
- Avia house style throughout, including chart labels: UK English, Arial, A4, no em or en
  dashes anywhere, author and last-modified-by set to "Avia Solutions", proofing language
  en-GB. Every chart states its unit and period and distinguishes actual from forecast.
- Do not change a forecast number without telling me first and measuring the effect.

**The work, in order.**

**First, the fleet productivity wedge**, pages 24 and 25 of the Boeing deck. Boeing shows
ASK growing 5.7%, seats 4.8% and fleet 3.1% over 2004-2023 and names the difference:
densification, up-gauging, longer stage lengths, more flights a day. We produce the ASK
and imply the fleet but do not explain the gap between them. Our whole 0.9 point shortfall
against Boeing has to live inside that wedge, so this slide either explains our number or
exposes it. Build it against the OAG store, which holds seats, frequency and stage length
by carrier and year.

**Then the six slides we can fill outright**, per the inventory: RPK recovery against 2019
with the domestic and international split; the top five international route areas; world
GDP by major economy, which is our own input; 25 years of traffic and network with airport
pairs, RPK and departures; LCC share of intra-regional capacity; and single-aisle seat
capacity by business model.

**Then bring me two decisions**: cargo, where we can fill none of the four slides and must
either buy the data or scope the OGF as passenger and airport cargo; and absolute fare
levels, the F15 item, without which we cannot draw the affordability slide that explains
the five regions where we lag Boeing worst.

**Deliverable:** a .pptx in the Observatory style, built by script so it regenerates when
the forecast moves, with the generating script committed. Not a hand-built file.

**What I want from you as you go:** tell me when a slide cannot be built and why, in one
line, rather than filling it with something approximate. A gap named is the point of the
exercise. And build the guard before the analysis: on 9 August an unmapped-airport report
caught three separate bugs that would each have produced a plausible-looking table.
