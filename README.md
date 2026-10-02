# CH+ overlapping-SPW self-calibration

This repository contains the CASA 6 self-calibration implementation used for
the CH$^+$(1--0) analysis described by Hayatsu (in preparation).  The motivating
Cycle 2 setup contains partially overlapping spectral windows (SPWs).  A real
line changes the mean signal in the line-bearing window, so an independent
amplitude solution for every SPW can absorb astrophysical SPW-to-SPW structure
into the gains.

The recommended reduction therefore derives phase and amplitude solutions from
explicitly selected line-free channels with `combine='scan,spw'` and maps the
common solution back to every science SPW.  The repository also retains a
clearly labelled independent-SPW failure-mode demonstration for controlled
comparison; it is not a recommended science reduction.

## Turnkey Cycle 2 benchmark scripts

The [`cycle2/`](cycle2/README.md) directory contains one recommended script and
one deliberately unsafe comparison script for each benchmark galaxy:

| Target | Recommended | Failure-mode demonstration |
|---|---|---|
| Cosmic Eyelash | `cycle2/eyelash_cy2_recommended.py` | `cycle2/eyelash_cy2_independent_spw.py` |
| G09v1.40 | `cycle2/g09v140_cy2_recommended.py` | `cycle2/g09v140_cy2_independent_spw.py` |
| G09v1.124 | `cycle2/g09v1124_cy2_recommended.py` | `cycle2/g09v1124_cy2_independent_spw.py` |

Each file is standalone: it embeds the target-specific field, line-free
frequency ranges, reference antenna, phase centre, expected SPW count, and line
imaging reference frequency.  Put the corresponding pipeline-calibrated Cycle
2 measurement set in a fresh working directory as `calibrated.ms`, then run one
script, for example:

```bash
casa --nogui --nologger --nologfile --agg \
  -c /path/to/chplus-selfcal/cycle2/eyelash_cy2_recommended.py
```

The input measurement set is not modified.  The script writes its products to
a new target- and mode-specific directory and stops rather than overwriting an
existing directory.  It performs target splitting, continuum modelling, phase
and amplitude gain calibration, continuum subtraction, and creation of a
non-deconvolved line cube.  The exact run parameters and output paths are saved
to `provenance.json`.

The recommended and comparison scripts differ intentionally only in the
amplitude solution and its application:

- recommended: `combine='scan,spw'` and a common SPW map;
- failure-mode demonstration: `combine='scan'` and an identity SPW map, which
  permits independent amplitude gains in each SPW.

Search each script for `ここ` to find the exact `gaincal` and `applycal`
choices responsible for this difference.

At the end of a successful run, each script also extracts the dirty-cube
spectrum at the continuum-peak position and writes
`<target>.diagnostic_spectrum.png` and `.pdf` in the same target/mode output
directory as the CASA products.  This quick-look spectrum uses one image pixel
and is labelled as diagnostic only; it is not the aperture-integrated science
spectrum used for line measurements.

## Configurable interface

`chplus_selfcal.py` and `chplus_selfcal.example.json` provide a configurable
interface for adapting the recommended combined-SPW workflow to another
dataset.  Every dataset-specific value must be verified before use:

```bash
casa --nogui --nologger --nologfile --agg \
  -c chplus_selfcal.py path/to/config.json
```

## CASA compatibility

The six benchmark scripts load under CASA 6.7.5.  In CASA 6.7 and later they
call the retained `uvcontsub_old` task because the replacement `uvcontsub` task
does not support `combine='spw'`; earlier CASA 6 releases use their original
`uvcontsub` task automatically.

The embedded SPW counts, frequency coverage, and reference antennas were
checked against the saved target-only Cycle 2 measurement sets.  This validates
the recorded inputs and installed CASA task interfaces, but is not a substitute
for rerunning and scientifically validating every final product.

## Validation required after a run

- inspect phase and amplitude solution S/N and antenna coverage;
- verify that the relative SPW flux scale and continuum level are preserved;
- compare calibrated and pipeline spectra using the same aperture and channel
  binning;
- inspect flagged-data fractions, image residuals, and recovered integrated
  flux before adopting the output.

No ALMA measurement sets or proprietary data are included.  No software
license has yet been assigned; reuse terms should be clarified before a formal
archival release.
