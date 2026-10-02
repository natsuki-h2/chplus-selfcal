#!/usr/bin/env python3
"""Recommended Cycle 2 self-calibration for the Cosmic Eyelash.

Run with CASA 6 from a fresh directory containing only the appropriate
pipeline-calibrated measurement set named ``calibrated.ms``.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from casatasks import applycal, gaincal, split, tclean
from casatools import image as image_tool
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
# KEY CHOICE (ここ): combine the overlapping SPWs into one amplitude solution.
AMPLITUDE_COMBINE = "scan,spw"
MODE = "recommended_combined_spw"


def save_diagnostic_spectrum(continuum_image, line_image, output_dir):
    """Plot the dirty-cube spectrum at the continuum peak (diagnostic only)."""
    reader = image_tool()
    reader.open(str(continuum_image) + ".image")
    try:
        continuum = np.squeeze(np.asarray(reader.getchunk()))
    finally:
        reader.close()

    reader.open(str(line_image) + ".image")
    try:
        cube = np.squeeze(np.asarray(reader.getchunk()))
    finally:
        reader.close()

    if continuum.ndim != 2 or cube.ndim != 3:
        raise RuntimeError(
            f"Unexpected diagnostic image shapes: continuum={continuum.shape}, "
            f"cube={cube.shape}"
        )
    peak_x, peak_y = np.unravel_index(
        np.nanargmax(continuum), continuum.shape
    )
    line_x = int(round(peak_x - (continuum.shape[0] - 1) / 2
                       + (cube.shape[0] - 1) / 2))
    line_y = int(round(peak_y - (continuum.shape[1] - 1) / 2
                       + (cube.shape[1] - 1) / 2))
    line_x = int(np.clip(line_x, 0, cube.shape[0] - 1))
    line_y = int(np.clip(line_y, 0, cube.shape[1] - 1))
    spectrum_mjy = 1.0e3 * np.asarray(cube[line_x, line_y, :], dtype=float)

    figure_base = output_dir / f"{TAG}.diagnostic_spectrum"
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.step(np.arange(spectrum_mjy.size), spectrum_mjy, where="mid",
            color="#1f77b4", linewidth=1.3)
    ax.axhline(0.0, color="0.35", linewidth=0.8)
    ax.set_xlabel("Spectral channel (25 km s$^{-1}$ spacing)")
    ax.set_ylabel("Dirty-cube intensity (mJy beam$^{-1}$)")
    ax.set_title(f"{SOURCE}: {MODE.replace('_', ' ')}")
    ax.text(0.02, 0.96, "Continuum-peak pixel; diagnostic only",
            transform=ax.transAxes, ha="left", va="top", fontsize=9)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(str(figure_base) + ".png", dpi=180)
    fig.savefig(str(figure_base) + ".pdf")
    plt.close(fig)
    return str(figure_base) + ".png", str(figure_base) + ".pdf"


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
        # KEY CHOICE (ここ): this is "scan,spw" in the recommended reduction.
        spw=LINE_FREE_SPW, solint="8000s", combine=AMPLITUDE_COMBINE,
        refant=REFERENCE_ANTENNA, refantmode="flex", minblperant=4,
        minsnr=3.0, gaintype="G", calmode="ap", solnorm=False,
        gaintable=[str(phase_table)], spwmap=common_map,
    )
    applycal(
        vis=str(target_ms), field=SOURCE,
        gaintable=[str(phase_table), str(amplitude_table)],
        # KEY CHOICE (ここ): map the common amplitude solution to every SPW.
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

    diagnostic_png, diagnostic_pdf = save_diagnostic_spectrum(
        continuum_image, line_image, output_dir
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
        "diagnostic_plot_png": diagnostic_png,
        "diagnostic_plot_pdf": diagnostic_pdf,
    }
    (output_dir / "provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(provenance, indent=2))


if __name__ == "__main__":
    main()
