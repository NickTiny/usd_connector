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
import textwrap

# Make `pxr` module available, for running as `bpy` PIP package.
bpy.utils.expose_bundled_modules()

import pxr.Gf as Gf
import pxr.Sdf as Sdf
import pxr.Usd as Usd
import pxr.UsdShade as UsdShade


class USDConnectorMetadataSet(bpy.types.USDHook):
    """Example implementation of USD IO hooks"""
    bl_idname = "usd_hook_example"
    bl_label = "usd_connector_metadata_set"

    @staticmethod
    def on_import(import_context):
        """ Set metadata on imported data blocks for use in generation of USD Overrides and resyncing."""
        # Get prim to data block mapping
        prim_map = import_context.get_prim_map()
        
        # Store prim path as a string on each data block created
        for prim_path, data_blocks in prim_map.items():
            for data_block in data_blocks:
                data_block["prim_path"] = str(prim_path)


def register():
    bpy.utils.register_class(USDConnectorMetadataSet)


def unregister():
    bpy.utils.unregister_class(USDConnectorMetadataSet)