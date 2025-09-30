import bpy
import os
from . import core
from pathlib import Path
import shutil

###########################################################
# Add Reference / Import
###########################################################


class USDConnectorAddReference(bpy.types.Operator):
    bl_idname = "usd.connector_add_reference_import"
    bl_label = "Import USD as Reference"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")  # type: ignore

    def draw(self, context) -> None:
        layout = self.layout
        layout.prop(self, "filepath", text="USD File Path")

    def execute(self, context) -> {'FINISHED'}:
        core.import_usd_reference(self.filepath)
        return {'FINISHED'}

    def invoke(self, context, event) -> {'RUNNING_MODAL'}:
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


############################################################
# Create Layer / Export
############################################################
class USDConnectorExportLayer(bpy.types.Operator):
    bl_idname = "usd.connector_exporter"
    bl_label = "Export USD as Layer"
    bl_description = "" # TODO Description
    bl_options = {'REGISTER', 'UNDO'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")  # type: ignore

    def execute(self, context) -> {'FINISHED'}:
        if len(context.scene.usd_connect_libraries) != 1:
            self.report({'ERROR'}, "USD Library not found.")
            return {'CANCELLED'}

        core.export_usd_layer(Path(self.filepath))
        return {'FINISHED'}

    def invoke(self, context, event) -> {'RUNNING_MODAL'}:
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


############################################################
# Refresh Library
############################################################
class USDConnectLibraryRefresh(bpy.types.Operator):
    bl_idname = "usd.connector_library_refresh"
    bl_label = "Refresh USD Reference"
    bl_description = "Export current USD library overrides to the export path"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context) -> {'FINISHED'}:
        if len(context.scene.usd_connect_libraries) != 1:
            self.report({'ERROR'}, "USD Library not found.")
            return {'CANCELLED'}

        # Export the current overrides
        core.refresh_usd_library()
        return {'FINISHED'}


classes = [
    USDConnectorAddReference,
    USDConnectorExportLayer,
    USDConnectLibraryRefresh,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls) 
