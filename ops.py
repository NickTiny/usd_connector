import bpy
import os
from . import core
from .usd_hook import USDConnectorMetadataSet
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

        bpy.utils.register_class(USDConnectorMetadataSet)
        core.import_usd_reference(self.filepath)
        bpy.utils.unregister_class(USDConnectorMetadataSet)

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

        bpy.utils.register_class(USDConnectorMetadataSet)
        core.export_usd_layer(Path(self.filepath))
        bpy.utils.unregister_class(USDConnectorMetadataSet)

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
        bpy.utils.register_class(USDConnectorMetadataSet)
        core.refresh_export_usd_layer()
        bpy.utils.unregister_class(USDConnectorMetadataSet)

        # TODO setting interval to wait for export to finish need programmatic way to ensure export is complete
        bpy.app.timers.register(library_refresh_import)

        return {'FINISHED'}


def library_refresh_import() -> None:
    """Remove all objects associated with a given library name"""
    library = bpy.context.scene.usd_connect_libraries[-1]

    old_objs = []
    for obj in bpy.context.scene.objects:
        if obj.usd_connect_props.library_name == library.name:
            obj.name = "OLD_" + obj.name
            old_objs.append(obj)

    bpy.utils.register_class(USDConnectorMetadataSet)

    core.import_usd_reference(library.file_path, library.export_path)

    bpy.utils.unregister_class(USDConnectorMetadataSet)

    new_objs = [
        obj
        for obj in core.get_library_objects(library)
        if not obj.name.startswith("OLD_")
    ]

    # # Remap old objects to new objects based on root prim path
    remap_dict = {}
    unmapped_objs = []
    for old_obj in old_objs:
        matched = False
        for new_obj in new_objs:
            if (
                old_obj.usd_connect_props.prim_path
                == new_obj.usd_connect_props.prim_path
            ):
                remap_dict[old_obj] = new_obj
                matched = True
                break
        if not matched:
            unmapped_objs.append(old_obj)

    for old_obj, new_obj in remap_dict.items():
        old_obj.user_remap(new_obj)

    # Remove Unused Objects
    for unmapped_obj in unmapped_objs:
        bpy.data.objects.remove(unmapped_obj, do_unlink=True)


# class USDConnectRefreshExport(bpy.types.Operator):
#     bl_idname = "usd.connector_library_export"
#     bl_label = "Export USD Library Overrides"
#     bl_description = "Export current USD library overrides to the export path"
#     bl_options = {'REGISTER', 'UNDO'}

#     def execute(self, context) -> {'FINISHED'}:
#         if len(context.scene.usd_connect_libraries) != 1:
#             self.report({'ERROR'}, "USD Library not found.")
#             return {'CANCELLED'}

#         bpy.utils.register_class(USDConnectorMetadataSet)
#         library = context.scene.usd_connect_libraries[-1]

#         # Export the current overrides
#         bpy.ops.wm.usd_export(filepath=TARGET_EXPORT)

#         bpy.utils.unregister_class(USDConnectorMetadataSet)
#         return {'FINISHED'}


# class USDConnectLibraryReimport(bpy.types.Operator):
#     bl_idname = "usd.connector_library_reimport"
#     bl_label = "Reimport USD Library"
#     bl_description = "Delete existing USD library objects and reimport from export file"
#     bl_options = {'REGISTER', 'UNDO'}

#     def execute(self, context) -> {'FINISHED'}:
#         if len(context.scene.usd_connect_libraries) != 1:
#             self.report({'ERROR'}, "USD Library not found.")
#             return {'CANCELLED'}

#         bpy.utils.register_class(USDConnectorMetadataSet)
#         library = context.scene.usd_connect_libraries[-1]

#         # Delete all USD Scene Data
#         to_remove = []
#         for obj in context.scene.objects:
#             if obj.usd_connect_props.library_name == library.name:
#                 obj.name = "OLD_" + obj.name
#                 to_remove.append(obj)

#         # Re-import the library from override file
#         os.environ["USD_CONNECT_STAGE_PATH"] = LIBRARY_SOURCE_FILE
#         bpy.ops.wm.usd_import(filepath=LAYER_FILE)

#         # # Importer will reset library filepath need to re-adjust
#         # library = context.scene.usd_connect_libraries[-1]
#         # library.file_path = LIBRARY_SOURCE_FILE

#         bpy.utils.unregister_class(USDConnectorMetadataSet)
#         # del os.environ["USD_CONNECT_STAGE_PATH"]

#         for obj in to_remove:
#             bpy.data.objects.remove(obj, do_unlink=True)

#         return {'FINISHED'}


# class USDConnectLibraryRefresh(bpy.types.Macro):
#     bl_idname = "usd.connector_library_refresh"
#     bl_label = "Refresh USD Library"
#     bl_description = "Export overrides and reimport USD library"
#     bl_options = {'REGISTER', 'UNDO'}


# def register_library_refresh_macro():
#     """Register the macro operations in the correct order"""
#     op = USDConnectLibraryRefresh.define("usd.connector_library_export")
#     op = USDConnectLibraryRefresh.define("usd.connector_library_reimport")


classes = [
    USDConnectorAddReference,
    # USDConnectorAddReferenceSnapshot,
    # USDConnectorAddReference,
    USDConnectorExportLayer,
    USDConnectLibraryRefresh,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    # register_add_reference_macro()

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls) 
