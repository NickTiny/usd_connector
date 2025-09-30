import bpy

from .ops import (
    USDConnectorAddReference,
    USDConnectorExportLayer,
    USDConnectLibraryRefresh,
)


class USDConnectMenu(bpy.types.Menu):
    bl_idname = "USD_MT_usd_connector_menu"
    bl_label = "USD Connector"

    def draw(self, context) -> None:
        layout = self.layout
        layout.operator(USDConnectorAddReference.bl_idname, icon='IMPORT')
        layout.operator(USDConnectLibraryRefresh.bl_idname, icon='FILE_REFRESH')
        layout.operator(USDConnectorExportLayer.bl_idname, icon='EXPORT')

def append_menu(self, context) -> None:
    layout = self.layout
    layout.menu("USD_MT_usd_connector_menu")


def register():
    bpy.utils.register_class(USDConnectMenu)
    bpy.types.TOPBAR_MT_file.append(append_menu)

def unregister():
    bpy.utils.unregister_class(USDConnectMenu)
    bpy.types.TOPBAR_MT_file.remove(append_menu)
