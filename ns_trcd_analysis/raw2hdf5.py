import click
import numpy as np
import h5py
from itertools import product
from typing import List
from .core import count_subdirs


def ingest(input_dir, output_file_path, incremental) -> None:
    """Read the contents of an experiment directory into an HDF5 file.

    If 'incremental' is True, then each shot will be written to the HDF5 file
    after it is read, otherwise data is read into a temporary array and saved at
    the very end. The incremental approach is much slower, but is useful when the
    machine doing the analysis has limited memory.

    The directory must have this layout:
    <input dir>
        <shot dir> (one for each shot)
            par.npy
            perp.npy
            ref.npy
    
    The HDF5 file will have two datasets: "data" and "wavelengths". The "data" dataset contains
    one large array with all of the experiment data. The array has these dimensions:
    (20000, 3, <num shots>, <num wavelengths>, 1)

    At the experiment time resolution (20ns for 400us) you get 20,000 points. There are 3 channels
    (parallel, perpendicular, and reference). The last dimension is the number of pump states. This
    is now 1 (there's always a pump state), but it is retained for backwards compatibility.
    """
    num_shots = count_subdirs(input_dir)
    wls = collect_wavelengths(input_dir / "1")
    with h5py.File(output_file_path, "w") as outfile:
        if not incremental:
            tmp_arr = np.empty((20_000, 3, num_shots, len(wls), 1))
        outfile.create_dataset("data", (20_000, 3, num_shots, len(wls), 1))
        data = outfile["data"]
        outfile.create_dataset("wavelengths", (len(wls),), data=wls)
        dir_indices = [x for x in product(range(1, num_shots+1), range(len(wls)))]
        with click.progressbar(dir_indices, label="Reading data") as indices:
            for shot_index, wl_index in indices:
                datadir = input_dir / f"{shot_index}" / f"{wls[wl_index]}"
                # np.s_[...] generates the indices that you would normally get by slicing a NumPy array
                if incremental:
                    shotdata = np.empty((20_000, 3))
                    shotdata[:, 0] = np.load(datadir / "par.npy")
                    shotdata[:, 1] = np.load(datadir / "perp.npy")
                    shotdata[:, 2] = np.load(datadir / "ref.npy")
                    data.write_direct(shotdata, np.s_[:, :], np.s_[:, :, shot_index - 1, wl_index, 0])
                else:
                    tmp_arr[:, 0, shot_index - 1, wl_index, 0] = np.load(datadir / "par.npy")
                    tmp_arr[:, 1, shot_index - 1, wl_index, 0] = np.load(datadir / "perp.npy")
                    tmp_arr[:, 2, shot_index - 1, wl_index, 0] = np.load(datadir / "ref.npy")
        if not incremental:
            data.write_direct(tmp_arr, np.s_[:, :, :, :, :], np.s_[:, :, :, :, :])


def collect_wavelengths(path) -> List[int]:
    """Collect the wavelengths from a shot directory.
    """
    wls = []
    for d in path.iterdir():
        if d.name[0] == "_":
            continue
        if not d.is_dir():
            continue
        wls.append(int(d.name))
    return wls