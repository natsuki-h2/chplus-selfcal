#!/usr/bin/env python3
"""Recommended Cycle 2 self-calibration for the Cosmic Eyelash.

Run with CASA 6 from a fresh directory containing only the appropriate
pipeline-calibrated measurement set named ``calibrated.ms``.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from casatasks import applycal, gaincal, split, tclean
from casatools import msmetadata, version_string

try:
    from casatasks import uvcontsub_old as continuum_subtract
except ImportError:  # CASA releases before uvcontsub was renamed.
    from casatasks import uvcontsub as continuum_subtract

SOURCE = "Eyelash"
TAG = "eyelash"
LINE_FREE_SPW = "*:248.88~250.22GHz,*:251.89~253.37GHz"
REFERENCE_ANTENNA = "DA59"
PHASECENTER = "J2000 21h35m11.66 -01d02m52.46"
REST_FREQUENCY = "251054MHz"
EXPECTED_SPWS = 6
AMPLITUDE_COMBINE = "scan,spw"
MODE = "recommended_combined_spw"


def main():
    input_ms = (Path.cwd() / "calibrated.ms").resolve()
    output_dir = (Path.cwd() / f"{TAG}_cy2_{MODE}").resolve()
    if not input_ms.exists():
        raise FileNotFoundError(f"Required input not found: {input_ms}")
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {output_dir}")
    output_dir.mkdir()

    target_ms = output_dir / f"{TAG}.target.ms"
    split(vis=str(input_ms), outputvis=str(target_ms), field=SOURCE, datacolumn="all")

    metadata = msmetadata()
    metadata.open(str(target_ms))
    try:
        spws = sorted(int(value) for value in metadata.spwsforfield(SOURCE))
    finally:
        metadata.close()
    if len(spws) != EXPECTED_SPWS:
        raise RuntimeError(f"Expected {EXPECTED_SPWS} target SPWs, found {spws}")
    common_spw = min(spws)
    common_map = [common_spw] * (max(spws) + 1)

    continuum_image = output_dir / f"{TAG}.continuum.model"
    tclean(
        vis=str(target_ms), field=SOURCE, spw=LINE_FREE_SPW,
        datacolumn="corrected", imagename=str(continuum_image), specmode="mfs",
        phasecenter=PHASECENTER, imsize=[512, 512], cell="0.05arcsec",
        weighting="briggs", robust=0.5, niter=1000, threshold="0.0Jy",
        usemask="auto-multithresh", interactive=False,
        savemodel="modelcolumn", pbcor=False,
    )

    phase_table = output_dir / f"{TAG}.phase.cal"
    amplitude_table = output_dir / f"{TAG}.amplitude.cal"
    gaincal(
        vis=str(target_ms), caltable=str(phase_table), field=SOURCE,
        spw=LINE_FREE_SPW, solint="8000s", combine="scan,spw",
        refant=REFERENCE_ANTENNA, refantmode="flex", minblperant=4,
        minsnr=3.0, gaintype="G", calmode="p", solnorm=False,
    )
    gaincal(
        vis=str(target_ms), caltable=str(amplitude_table), field=SOURCE,
        spw=LINE_FREE_SPW, solint="8000s", combine=AMPLITUDE_COMBINE,
        refant=REFERENCE_ANTENNA, refantmode="flex", minblperant=4,
        minsnr=3.0, gaintype="G", calmode="ap", solnorm=False,
        gaintable=[str(phase_table)], spwmap=common_map,
    )
    applycal(
        vis=str(target_ms), field=SOURCE,
        gaintable=[str(phase_table), str(amplitude_table)],
        spwmap=[common_map, common_map], interp=["linear", "linear"],
        applymode="calonly", calwt=True, flagbackup=True,
    )

    calibrated_ms = output_dir / f"{TAG}.selfcal.ms"
    split(vis=str(target_ms), outputvis=str(calibrated_ms),
          field=SOURCE, datacolumn="corrected")
    continuum_subtract(vis=str(calibrated_ms), fitspw=LINE_FREE_SPW,
                       combine="spw", fitorder=0, want_cont=False)
    contsub_ms = Path(f"{calibrated_ms}.contsub")
    line_image = output_dir / f"{TAG}.line.dirty"
    tclean(
        vis=str(contsub_ms), field=SOURCE, datacolumn="corrected",
        imagename=str(line_image), specmode="cube", restfreq=REST_FREQUENCY,
        outframe="BARY", veltype="optical", width="25km/s", nchan=-1,
        phasecenter=PHASECENTER, imsize=[256, 256], cell="0.05arcsec",
        weighting="briggs", robust=0.5, niter=0, interactive=False, pbcor=True,
    )

    provenance = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "casa_version": version_string(), "source": SOURCE, "mode": MODE,
        "input_ms": str(input_ms), "target_spws": spws,
        "line_free_spw": LINE_FREE_SPW, "reference_antenna": REFERENCE_ANTENNA,
        "phase_combine": "scan,spw", "amplitude_combine": AMPLITUDE_COMBINE,
        "phase_spwmap": common_map, "amplitude_spwmap": common_map,
        "calibrated_ms": str(calibrated_ms), "contsub_ms": str(contsub_ms),
        "line_image": str(line_image) + ".image",
    }
    (output_dir / "provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(provenance, indent=2))


if __name__ == "__main__":
    main()
