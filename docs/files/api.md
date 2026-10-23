# Python API Reference

This page documents the main Python modules in BERA Tools using mkdocstrings.

## Tools API

::: beratools.tools.check_seed_line
::: beratools.tools.vertex_optimization
::: beratools.tools.centerline
::: beratools.tools.canopy_footprint_absolute
::: beratools.tools.line_footprint_relative
    options:
      members:
        - line_footprint_relative
::: beratools.tools.ground_footprint

## Core Algorithms

::: beratools.core.algo_centerline
    options:
      members:
        - CenterlineParams
        - CenterlineStatus
        - EndPointAnchorResult
        - centerline_is_valid
        - snap_end_to_end
        - find_centerline
        - find_corridor_polygon
        - process_single_centerline
        - find_centerlines
        - regenerate_centerline
        - SeedLine
        - orient_to_split
::: beratools.core.line_footprint_functions
    options:
      members:
        - dyn_canopy_cost_raster
        - split_line_fc
        - split_line_npart
        - split_into_segments
        - split_into_equal_nth_segments
        - generate_line_args
        - find_corridor_threshold
        - process_single_line_relative
        - multiprocessing_footprint_relative
        - main_line_footprint_relative
::: beratools.core.canopy_threshold_relative
    options:
      members:
        - OperationCancelledException
        - main_canopy_threshold_relative
        - rate_of_change
        - multiprocessing_RofC
        - split_line_fc
        - split_into_segments
        - multiprocessing_percentile
        - cal_percentile_ring
        - copyparallel_lineLRC

## Common Tool Utilities

::: beratools.tools.common
    options:
      members:
        - remove_nan_from_array
        - split_into_equal_Nth_segments
        - cut_line_by_length
        - chk_df_multipart
        - dyn_fs_raster_stdmean
        - dyn_smooth_cost
        - dyn_np_cost_raster
        - dyn_np_cc_map
        - generate_line_args_DFP_NoClip

## Pipeline

::: beratools.core.pipeline

## Constants

::: beratools.core.constants

## Logger

::: beratools.core.logger

## Tool Base

::: beratools.core.tool_base
