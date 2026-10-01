#!/usr/bin/env python3
"""Reproducible continuum self-calibration for overlapping CH+ spectral windows.

Run inside CASA 6::

    casa --nogui --nologger --nologfile --agg \
      -c scripts/chplus_selfcal.py scripts/chplus_selfcal.example.json

The input measurement set is never modified.  A working copy is created with
``split`` and all calibration is applied to that copy.  Existing outputs are
preserved unless ``overwrite`` is explicitly set to true in the configuration.
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from casatasks import applycal, gaincal, split, tclean
from casatools import msmetadata


REQUIRED = {
    "input_ms", "work_ms", "field", "line_free_spw", "reference_antenna",
    "mask", "phasecenter", "cell", "imsize", "output_prefix",
}


def remove_output(path: Path, overwrite: bool) -> None:
    """Remove an exact output path only when overwrite was requested."""
    if not path.exists():
        return
    if not overwrite:
        raise FileExistsError(f"Output exists: {path}; set overwrite=true to replace it")
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def remove_casa_products(prefix: Path, overwrite: bool) -> None:
    for suffix in ("image", "mask", "model", "pb", "psf", "residual", "sumwt"):
        remove_output(Path(f"{prefix}.{suffix}"), overwrite)


def main(config_path: str) -> None:
    config_file = Path(config_path).expanduser().resolve()
    config = json.loads(config_file.read_text(encoding="utf-8"))
    missing = sorted(REQUIRED - set(config))
    if missing:
        raise ValueError(f"Missing configuration keys: {', '.join(missing)}")

    overwrite = bool(config.get("overwrite", False))
    input_ms = Path(config["input_ms"]).expanduser().resolve()
    work_ms = Path(config["work_ms"]).expanduser().resolve()
    prefix = Path(config["output_prefix"]).expanduser().resolve()
    prefix.parent.mkdir(parents=True, exist_ok=True)
    if not input_ms.exists():
        raise FileNotFoundError(input_ms)

    remove_output(work_ms, overwrite)
    split(vis=str(input_ms), outputvis=str(work_ms), datacolumn="all",
          field=config["field"])

    metadata = msmetadata()
    metadata.open(str(work_ms))
    try:
        science_spws = [int(spw) for spw in metadata.spwsforfield(config["field"])]
    finally:
        metadata.close()
    if not science_spws:
        raise RuntimeError(f"No spectral windows found for field {config['field']}")

    solution_spw = int(config.get("solution_spw", min(science_spws)))
    spwmap = [solution_spw] * (max(science_spws) + 1)
    phase_table = Path(f"{prefix}.phase.cal")
    amplitude_table = Path(f"{prefix}.amplitude.cal")
    initial_image = Path(f"{prefix}.continuum.initial")
    calibrated_image = Path(f"{prefix}.continuum.selfcal")
    for path in (phase_table, amplitude_table):
        remove_output(path, overwrite)
    for image_prefix in (initial_image, calibrated_image):
        remove_casa_products(image_prefix, overwrite)

    imaging = dict(
        vis=str(work_ms), field=config["field"], spw=config["line_free_spw"],
        specmode="mfs", imagename=str(initial_image),
        imsize=config["imsize"], cell=config["cell"],
        phasecenter=config["phasecenter"], weighting=config.get("weighting", "briggs"),
        robust=float(config.get("robust", 0.5)), niter=int(config.get("niter", 1000)),
        threshold=config.get("threshold", "0.0Jy"), mask=config["mask"],
        interactive=False, savemodel="modelcolumn", pbcor=False,
    )
    tclean(**imaging)

    common_gain = dict(
        vis=str(work_ms), spw=config["line_free_spw"], field=config["field"],
        solint=config.get("solint", "inf"), combine="scan,spw",
        refant=config["reference_antenna"], refantmode="flex",
        minblperant=int(config.get("minblperant", 4)),
        minsnr=float(config.get("minsnr", 3.0)), gaintype="G",
    )
    gaincal(caltable=str(phase_table), calmode="p", **common_gain)
    gaincal(caltable=str(amplitude_table), calmode="ap",
            gaintable=[str(phase_table)], spwmap=spwmap, solnorm=False,
            **common_gain)

    applycal(
        vis=str(work_ms), field=config["field"],
        gaintable=[str(phase_table), str(amplitude_table)],
        spwmap=[spwmap, spwmap], applymode="calonly",
        calwt=bool(config.get("calwt", False)), flagbackup=True,
    )

    calibrated = dict(imaging)
    calibrated.update(imagename=str(calibrated_image),
                      datacolumn="corrected", savemodel="none")
    tclean(**calibrated)

    provenance = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "config_file": str(config_file), "input_ms": str(input_ms),
        "work_ms": str(work_ms), "science_spws": science_spws,
        "solution_spw": solution_spw, "spwmap": spwmap,
        "phase_table": str(phase_table), "amplitude_table": str(amplitude_table),
    }
    Path(f"{prefix}.provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(provenance, indent=2))


if __name__ == "__main__":
    candidates = [arg for arg in sys.argv[1:] if arg.endswith(".json")]
    if len(candidates) != 1:
        raise SystemExit("Pass exactly one JSON configuration file")
    main(candidates[0])
