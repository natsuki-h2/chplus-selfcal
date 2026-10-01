# CH+ overlapping-SPW self-calibration

This repository provides the CASA 6 self-calibration implementation used for
the CH+(1-0) analysis described by Hayatsu (in preparation).  It is designed
for spectral setups in which the astrophysical line occupies one or more
partially overlapping spectral windows.

The central methodological choice is to derive phase and amplitude solutions
from explicitly selected line-free channels with `combine='scan,spw'`, and to
map that common solution back to every science spectral window.  This preserves
the relative spectral-window flux scale; solving independent amplitudes per
window can instead absorb a real difference caused by line absorption.

## Run

Requires CASA 6 with `casatasks` and `casatools`.

1. Copy `chplus_selfcal.example.json` to a new configuration file.
2. Replace every dataset-specific entry, especially `line_free_spw`,
   `reference_antenna`, `solution_spw`, `mask`, `phasecenter`, and `solint`.
3. Run:

```bash
casa --nogui --nologger --nologfile --agg \
  -c chplus_selfcal.py path/to/config.json
```

The input measurement set is never modified.  The script creates a working
copy, calibration tables, before/after continuum images, and a provenance JSON
record.  Existing outputs are preserved unless `overwrite` is explicitly set
to `true`.

## Scope and limitations

- The example configuration records the Cosmic Eyelash setup; it is not a
  turnkey archive reduction.
- Line-free channels and the reference antenna must be verified independently
  for every target and execution block.
- A successful CASA run establishes that the code path works, not that the
  resulting calibration is scientifically valid.  Inspect solution S/N,
  antenna coverage, flux conservation, residuals, and the line profile before
  adopting a result.
- This release contains no ALMA measurement sets or proprietary data.

No software license has yet been assigned.  The files are publicly viewable,
but reuse terms should be clarified before a formal archival release.
