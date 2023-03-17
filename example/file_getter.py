#!/usr/bin/env python3
from pathlib import Path

def ensure_outdir_viable(outdir:Path):
    """Ensures outdir isn't a file and makes the directory, if needed
    
    Returns:
        Path(outdir)
    """

    if not type(outdir) == Path:
        outdir = Path(outdir).resolve()
    if outdir.is_dir(): return outdir
    if not outdir.exists():
        outdir.mkdir(exist_ok=True,parents=False)
        return outdir
    if outdir.is_file(): raise FileExistsError(f"Proposed `outdir` ({outdir}) already exists as a file.")

def get_example_config(outdir:Path):
    """Writes example config to `outdir`.

    Args:
        outdir (Path): output directory
    """

    infile = Path(__file__).parent / "gisaid_config.ini"
    outfile = outdir.joinpath("gisaid_config.ini").resolve()
    print(f"Writing out '{outfile}'")
    with infile.open() as fh, outfile.open('w') as out:
        for line in fh: out.write(line)
