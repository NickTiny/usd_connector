import bpy
from .usd_hook import USDConnectorMetadataSet


class USDConnectorImporter(bpy.types.Operator):
    bl_idname = "usd.connector_importer"
    bl_label = "Import USD with USD Connector"
    bl_description = "Import USD file with USD Connector, applying custom settings"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")  # type: ignore
    scale : bpy.props.FloatProperty(  # type: ignore
        name="Scale",
        description="Scale to apply to imported USD",
        default=1.0,
        min=0.0001,
        max=1000.0,
    )
    
    def draw(self, context) -> None:
        layout = self.layout
        layout.prop(self, "filepath", text="USD File Path")
        layout.prop(self, "scale", text="Scale")

    def execute(self, context) -> {'FINISHED'}:
        bpy.utils.register_class(USDConnectorMetadataSet)
        bpy.ops.wm.usd_import(filepath=self.filepath, scale=self.scale)
        bpy.utils.unregister_class(USDConnectorMetadataSet)
        
        library = context.scene.usd_connect_libraries[-1]
        library.import_scale = self.scale
        
        return {'FINISHED'}

    def invoke(self, context, event) -> {'RUNNING_MODAL'}:
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class USDConnectorImporter(bpy.types.Operator):
    bl_idname = "usd.connector_importer"
    bl_label = "Import USD Reference"
    bl_description = "" # TODO Description
    bl_options = {'REGISTER', 'UNDO'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")  # type: ignore
    scale : bpy.props.FloatProperty(  # type: ignore
        name="Scale",
        description="Scale to apply to imported USD",
        default=1.0,
        min=0.0001,
        max=1000.0,
    )

    def draw(self, context) -> None:
        layout = self.layout
        layout.prop(self, "scale", text="Scale")

    def execute(self, context) -> {'FINISHED'}:
        bpy.utils.register_class(USDConnectorMetadataSet)
        bpy.ops.wm.usd_import(filepath=self.filepath, scale=self.scale)
        bpy.utils.unregister_class(USDConnectorMetadataSet)

        return {'FINISHED'}

    def invoke(self, context, event) -> {'RUNNING_MODAL'}:
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class USDConnectorExporter(bpy.types.Operator):
    bl_idname = "usd.connector_exporter"
    bl_label = "Export USD Layer"
    bl_description = "" # TODO Description
    bl_options = {'REGISTER', 'UNDO'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")  # type: ignore

    def execute(self, context) -> {'FINISHED'}:
        if len(context.scene.usd_connect_libraries) != 1:
            self.report({'ERROR'}, "USD Library not found.")
            return {'CANCELLED'}

        bpy.utils.register_class(USDConnectorMetadataSet)
        bpy.ops.wm.usd_export(filepath=self.filepath)
        bpy.utils.unregister_class(USDConnectorMetadataSet)

        return {'FINISHED'}

    def invoke(self, context, event) -> {'RUNNING_MODAL'}:
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


classes = [
    USDConnectorImporter,USDConnectorExporter
]   

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls) 
