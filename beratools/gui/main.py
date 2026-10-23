"""
Copyright (C) 2025 Applied Geospatial Research Group.

This script is licensed under the GNU General Public License v3.0.
See <https://gnu.org/licenses/gpl-3.0> for full license details.

Author: Richard Zeng

Description:
    This script is part of the BERA Tools.
    Webpage: https://github.com/BERATool/beratools

    Main entry point of BERA Tools.
"""
## Set GDAL_DATA path to avoid GDAL
# warning: Warning 3: Cannot find gdalvrt.xsd (GDAL_DATA is not defined)#
import os
import sys
import pathlib

# Configure GDAL immediately
env_root = pathlib.Path(sys.executable).parent

gdal_data = env_root / "Library" / "share" / "gdal"
if gdal_data.exists():
    os.environ["GDAL_DATA"] = str(gdal_data)

proj_data = env_root / "Library" / "share" / "proj"
if proj_data.exists():
    os.environ["PROJ_LIB"] = str(proj_data)

# Import after environment variables are set
from beratools.gui.bt_gui_main import runner

def gui_main():
    runner()

if __name__ == "__main__":
    runner()
