import bpy


class USDConnectLibraries(bpy.types.PropertyGroup):
    """Information specific to each Library is stored here."""

    name : bpy.props.StringProperty(  # type: ignore
        name="Name",
        description="Name of the USD library that was imported",
        default="",
    )

    file_path : bpy.props.StringProperty(  # type: ignore
        name="File Path",
        description="Path to the USD file that was imported, used as a library/reference.",
        default="",
    )

    file_path_snapshot : bpy.props.StringProperty(  # type: ignore
        name="File Path Snapshot",
        description=(
            "Snapshot of the USD file used at the time of import, used to calculate differences "
            "between blend and USD data to generate overrides."
        ),
        default="",
    )

    root_prim_path: bpy.props.StringProperty(  # type: ignore
        name="Root Prim Path",
        description="Path to the root prim of the imported USD file",
        default="",
    )

    export_path: bpy.props.StringProperty(  # type: ignore
        name="Export Path",
        description="Path to export the USD override file to",
        default="",
        subtype="FILE_PATH",
    )


class USDConnectIDProps(bpy.types.PropertyGroup):
    """Information specific to each Prim is stored here."""

    prim_path : bpy.props.StringProperty(  # type: ignore
        name="Prim Path",
        description="Path to the USD prim that this object represents",
        default="",
    )

    library_name : bpy.props.StringProperty(  # type: ignore
        name="Library Name",
        description="Name of the USD library that this prim came from",
        default="",
    )

    # TODO Pointer to collections in UI sometimes slow down performance. Scene may as well, requires investigation.
    # Only matters if used in UI
    library_scene : bpy.props.PointerProperty(  # type: ignore
        name="Library Scene",
        type=bpy.types.Scene,
        description="Scene that contains the library this prim came from",
    )

    def library_get(self) -> USDConnectLibraries | None:
        """Get the library object this prim came from."""
        if self.library_scene:
            return self.library_scene.usd_connect_libraries.get(self.library_name)
        return None


class USDConnectSessionState(bpy.types.PropertyGroup):

    active: bpy.props.BoolProperty(  # type: ignore
        name="Active",
        description="Whether USD Connect is active in this session",
        default=False,
    )

    refresh: bpy.props.BoolProperty(  # type: ignore
        name="Refresh",
        description="Whether a refresh operation is in progress",
        default=False,
    )


# ----------------REGISTER--------------.

classes = [
    USDConnectLibraries,
    USDConnectIDProps, 
    USDConnectSessionState
]


def register():

    for cls in classes:
        bpy.utils.register_class(cls)

    # Scene Properties.
    bpy.types.ID.usd_connect_props = bpy.props.PointerProperty(
        name="USD Connect",
        type=USDConnectIDProps,
        description="Metadata about this object's source Prim and USD file",
    )
    bpy.types.Scene.usd_connect_libraries = bpy.props.CollectionProperty(
        name="USD Libraries",
        type=USDConnectLibraries,
        description="List of USD libraries that have been imported into this scene",
    )
    bpy.types.WindowManager.usd_connect_session = bpy.props.PointerProperty(
        name="USD Connect Session",
        type=USDConnectSessionState,
        description="State information about the current USD Connect session",
    )


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    del bpy.types.ID.usd_connect_props
    del bpy.types.Scene.usd_connect_libraries
    del bpy.types.WindowManager.usd_connect_session
