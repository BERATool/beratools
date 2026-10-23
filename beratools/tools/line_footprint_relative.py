# ---------------------------------------------------------------------------
#    Copyright (C) 2021  Applied Geospatial Research Group
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://gnu.org/licenses/gpl-3.0>.
#
# ---------------------------------------------------------------------------
#
# line_footprint_relative.py
# Script Author: Maverick Fong
# Date: 2023-May
# Use open sources python library for produce dynamic footprint
# from dynamic canopy and cost raster with lines and CHM input.
# Prerequisite:  Line feature class must have the attribute Fields: "OLnFID" adn CHM raster
# line_footprint_relative.py
# This script is part of the BERA toolset
# Webpage: https://github.com/
#
# Purpose: Creates dynamic footprint polygons for each input line based on a least
# cost corridor method and individual line thresholds.
#
# ---------------------------------------------------------------------------

from beratools.core.line_footprint_functions import *
from beratools.core.canopy_threshold_relative import *
import time


def line_footprint_relative(
    in_line,
    in_chm,
    max_ln_width,
    exp_shk_cell,
    out_footprint,
    out_centerline,
    off_ln_dist,
    canopy_percentile,
    canopy_thresh_percentage,
    tree_radius,
    max_line_dist,
    canopy_avoidance,
    exponent,
    processes,
    call_mode,
    log_level,
):
    """Create canopy footprint polygons using per-line relative canopy thresholds.

    Runs in two steps. First, `main_canopy_threshold_relative` samples the CHM on
    both sides of each input line and derives an individual canopy threshold
    height from the surrounding forest. Second, `main_line_footprint_relative`
    builds a canopy and cost raster per line and traces a least cost corridor
    to produce the footprint polygons and, optionally, centerlines. Results are
    written to `out_footprint` and `out_centerline`; if the threshold step
    fails, an error is printed and nothing is written.

    Numeric arguments may be passed as strings (as they are from the GUI) and
    are converted before use.

    Args:
        in_line: Input line file.
        in_chm: CHM raster used to calculate the surrounding forest percentile
            and to build the canopy and cost rasters.
        max_ln_width: Maximum processing width for input lines. A large value
            increases processing time; a small value may clip the footprint.
        exp_shk_cell: Cell range used to expand and shrink the corridor before
            polygons are generated, to remove small artifacts. Use 0 when the
            cell size is 1 m or larger.
        out_footprint: Output footprint polygon file.
        out_centerline: Optional output centerline file.
        off_ln_dist: Offset distance from input lines. Currently not used.
        canopy_percentile: Nth percentile of the surrounding forest height.
        canopy_thresh_percentage: Percentage of the canopy percentile height
            used as the canopy threshold.
        tree_radius: Radius of canopy influence in the cost raster. Smooths the
            canopy so gaps in sparse vegetation are not taken as footprint.
        max_line_dist: Maximum euclidean distance from canopy, a second
            smoothing factor that centers the line in the footprint.
        canopy_avoidance: Weight between tree search radius (near 0) and
            euclidean distance (near 1) in the cost raster.
        exponent: Exponent applied to the cost of vegetated areas.
        processes: Number of parallel processes.
        call_mode: How the tool was invoked (see `CallMode`).
        log_level: Logging level. Currently not used.
    """
    verbose = True if call_mode == CallMode.GUI.value else False

    dy_cl_line = main_canopy_threshold_relative(
        in_line=in_line,
        in_chm=in_chm,
        canopy_percentile=int(float(canopy_percentile)),
        canopy_thresh_percentage=int(float(canopy_thresh_percentage)),
        full_step=bool(True),
        processes=int(float(processes)),

    )

    if not dy_cl_line:
        print("[error]: main_canopy_threshold_relative did not return a valid path. Aborting footprint step.")
        return

    main_line_footprint_relative(
        in_line=dy_cl_line,
        in_chm=in_chm,
        max_ln_width=float(max_ln_width),
        out_footprint=out_footprint or "",
        out_centerline=out_centerline or "",
        exp_shk_cell=int(float(exp_shk_cell)),
        tree_radius=float(tree_radius),
        max_line_dist=float(max_line_dist),
        canopy_avoidance=float(canopy_avoidance),
        exponent=float(exponent),
        full_step=bool(True),
        canopy_thresh_percentage=int(float(canopy_thresh_percentage)),
        processes=int(float(processes)),
    )

if __name__ == "__main__":
    from beratools.utility.tool_args import CallMode, compose_tool_kwargs
    start_time = time.time()
    print("[info]: Dynamic CC and Footprint processing started")
    print("[info]: Current time: {}".format(time.strftime("%d %b %Y %H:%M:%S", time.localtime())))

    args=compose_tool_kwargs("line_footprint_relative")

    line_footprint_relative(**args)

    print("{}%".format(100))
    print("[info]: Dynamic CC and Footprint processes finished")
    print("[info]: Current time: {}".format(time.strftime("%d %b %Y %H:%M:%S", time.localtime())))
    print("[info]: Total processing time (seconds): {}".format(round(time.time() - start_time, 3)))
