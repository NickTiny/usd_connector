import bpy

from .ops import USDConnectorImporter, USDConnectorExporter


class USDConnectMenu(bpy.types.Menu):
    bl_idname = "USD_MT_usd_connector_menu"
    bl_label = "USD Connector"

    def draw(self, context) -> None:
        layout = self.layout
        layout.operator(USDConnectorImporter.bl_idname)
        layout.operator(USDConnectorExporter.bl_idname)
        
        
def append_menu(self, context) -> None:
    layout = self.layout
    layout.menu("USD_MT_usd_connector_menu")

    
def register():
    bpy.utils.register_class(USDConnectMenu)
    bpy.types.TOPBAR_MT_file_import.append(append_menu)

def unregister():
    bpy.utils.unregister_class(USDConnectMenu)
    bpy.types.TOPBAR_MT_file_import.remove(append_menu) 