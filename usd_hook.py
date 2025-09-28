# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
import bpy

bl_info = {
    "name": "USD Hook Example",
    "blender": (4, 4, 0),
}

import bpy
import bpy.types
from pathlib import Path

# Make `pxr` module available, for running as `bpy` PIP package.
bpy.utils.expose_bundled_modules()

from pxr import Sdf, Usd

class USDConnectorMetadataSet(bpy.types.USDHook):
    """Example implementation of USD IO hooks"""
    bl_idname = "usd_hook_example"
    bl_label = "usd_connector_metadata_set"

    @staticmethod
    def on_import(import_context) -> None:
        """ Set metadata on imported data blocks for use in generation of USD Overrides and resyncing."""
        # Get prim to data block mapping
        prim_map: dict[Sdf.Path, list[bpy.types.ID]] = import_context.get_prim_map()

        stage: Usd.Stage = import_context.get_stage()

        library = bpy.context.scene.usd_connect_libraries.add()
        library.name = Path(stage.GetRootLayer().realPath).name
        library.file_path = stage.GetRootLayer().realPath

        # Store prim path as a string on each data block created
        for prim_path, data_blocks in prim_map.items():
            prim_path: Sdf.Path
            data_blocks: list[bpy.types.ID]
            for data_block in data_blocks:
                usdprops = data_block.usd_connect_props
                usdprops.prim_path = str(prim_path)
                usdprops.library_name = library.name
                usdprops.library_scene = library.id_data

        print(usdprops.library_get())


def register():
    bpy.utils.register_class(USDConnectorMetadataSet)


def unregister():
    bpy.utils.unregister_class(USDConnectorMetadataSet)
