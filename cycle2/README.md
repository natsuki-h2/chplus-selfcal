# Cycle 2 benchmark scripts

This directory contains six self-contained CASA 6 scripts: one recommended
reduction and one deliberately unsafe, independent-SPW demonstration for each
of the three benchmark galaxies.

| Target | Recommended script | Independent-SPW demonstration |
|---|---|---|
| Cosmic Eyelash | `eyelash_cy2_recommended.py` | `eyelash_cy2_independent_spw.py` |
| G09v1.40 | `g09v140_cy2_recommended.py` | `g09v140_cy2_independent_spw.py` |
| G09v1.124 | `g09v1124_cy2_recommended.py` | `g09v1124_cy2_independent_spw.py` |

Each script is intentionally standalone.  No configuration file, mask, or
helper module is required.  Put the appropriate ALMA pipeline-calibrated Cycle
2 measurement set in an otherwise empty working directory as
`calibrated.ms`, then run exactly one script from that directory, for example:

```bash
casa --nogui --nologger --nologfile --agg \
  -c /path/to/chplus-selfcal/cycle2/eyelash_cy2_recommended.py
```

The scripts split the target, make a continuum model from the documented
line-free frequencies, solve phase and amplitude gains, apply them, subtract
the continuum, and make a non-deconvolved line cube.  They also write a JSON
record of the parameters used.  An existing output directory causes a safe
failure rather than an overwrite.

For CASA 6.7 and later, the scripts call the retained `uvcontsub_old` task
because the replacement `uvcontsub` task does not support `combine='spw'`.
Earlier CASA 6 releases use their original `uvcontsub` task automatically.

The recommended and demonstration scripts use the same target selection,
continuum model, phase solution, line-free channels, and imaging parameters.
The controlled difference is the amplitude solution:

- **Recommended:** `combine='scan,spw'`; one amplitude solution is mapped to
  every partially overlapping spectral window.
- **Independent-SPW demonstration:** `combine='scan'`; each spectral window
  receives its own amplitude solution.  This is retained only to reproduce the
  failure mode discussed in the paper.  It can absorb real SPW-to-SPW spectral
  structure into the gains and must not be adopted as the science reduction.

The exact amplitude-solution and SPW-mapping lines are marked with
`KEY CHOICE (ここ)` or `CONTROLLED FAILURE MODE (ここ)` comments in every
script.

Each run ends by plotting the dirty-cube spectrum at the continuum-peak
position.  The PNG and PDF quick-look figures are saved alongside the other
CASA products in the target/mode output directory.  They use a single pixel
and are intended to make the effect of the calibration choice immediately
visible, not to replace an aperture-integrated science spectrum.

The frequency selections and antenna choices were transcribed from the saved
Cycle 2 CASA task records used in the analysis.  The scripts assume that
`calibrated.ms` is the corresponding calibrated archive product for the named
target; they verify the target field and expected number of target SPWs before
solving.
