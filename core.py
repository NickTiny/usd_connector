import bpy
from pathlib import Path

# Make `pxr` module available, for running as `bpy` PIP package.
bpy.utils.expose_bundled_modules()

from pxr import Usd, UsdGeom, Sdf, Gf
from typing import List, Any, Union
from . import constants
import math
import os
import shutil
import tempfile
import contextlib
from bpy.types import Object, ViewLayer
from .prim_transfer import PrimTransfer

###############################################################
# Export / Import Operations
###############################################################
def import_usd_reference(ref_file_path: str, ref_stage=None):
    """Import a USD reference file and set up the library and prim mappings.

    NOTE: Must be called with hook registered, similar to direct operator call"""
    if not ref_stage:
        ref_stage = ref_file_path

    ref_pathlib = Path(ref_file_path)
    libraries = bpy.context.scene.usd_connect_libraries

    # TODO Due to exporter limitations we only support one library for now
    libraries.clear()
    library = libraries.add()

    # Setup Basic Library Info
    library.name = ref_pathlib.name
    library.ref_file_path = ref_file_path

    # Set Snapshot Path
    snapshot_dir = ref_pathlib.parent.joinpath("usd_snapshots")
    library.snapshot_file_path = snapshot_dir.joinpath(
        "snapshot_" + ref_pathlib.name
    ).as_posix()

    # Set Export Path
    library.export_path = ref_pathlib.parent.joinpath(
        "layer_" + ref_pathlib.name
    ).as_posix()

    with override_usd_session_state(active=True):
        bpy.ops.wm.usd_import("EXEC_DEFAULT", filepath=ref_stage)

    bpy.app.timers.register(import_create_usd_snapshot, first_interval=1.0)


def export_usd_layer(
    target_filepath: Path,
    selected_objects_only: bool = False,
    session_active: bool = True,
    session_refresh: bool = False,
) -> None:
    """Export the current scene to a USD file and generate overrides for the current library.

    NOTE: Must be called with hook registered, similar to direct operator call"""

    library = bpy.context.scene.usd_connect_libraries[0]

    # Store Actual Export Path in Library
    library.export_path = target_filepath.as_posix()

    # Pass Temp Path to Operator, to generate full USD file first
    # Hook will execute to generate override file at target filepath
    tmp_filepath = target_filepath.parent.joinpath("tmp_" + target_filepath.name)

    with override_usd_session_state(active=session_active, refresh=session_refresh):

        bpy.ops.wm.usd_export(
            filepath=tmp_filepath.as_posix(),
            selected_objects_only=selected_objects_only,
        )

    # Delete Temp File after Layer is generated
    if tmp_filepath.exists():
        tmp_filepath.unlink()


def import_create_usd_snapshot():
    library = bpy.context.scene.usd_connect_libraries[-1]
    shutil.copy(library.ref_file_path, library.snapshot_file_path)


##############################################################
# Refresh Functions
##############################################################


def refresh_usd_library() -> Path:
    workspace = Path(tempfile.mkdtemp(prefix="usd_refresh_"))
    refresh_export_usd_layer(workspace)


def refresh_export_usd_layer(tmp_dir: Path) -> None:
    """Import a USD reference file and set up the library and prim mappings.

    Args:
        source_filepath (str): The file path of the source USD file to be used for overriding.
        file_to_load (str | None, optional): Override the USD file to load. Defaults to None.
    """
    library = bpy.context.scene.usd_connect_libraries[0]

    library_objects = get_library_objects(library)

    export_path = tmp_dir.joinpath("refresh_export.usda")

    # Create an export aginst the snapshot file as opposed to the actual source file
    # This way we can detect what changed since the last refresh and later
    # Store these changes as overrides againist the snapshot
    # Later we can reaload these overrides but againist the actual source file
    # This way we can keep changes even if the source file changed
    with override_library_filepaths(library, library.snapshot_file_path):
        with override_object_selection(
            objects=library_objects, view_layer=bpy.context.view_layer
        ):
            export_usd_layer(
                export_path,
                selected_objects_only=True,
                session_active=True,
                session_refresh=True,
            )

    export_stage = Usd.Stage.Open(export_path.as_posix())
    export_stage.GetRootLayer().subLayerPaths.replace(
        library.snapshot_file_path, library.ref_file_path
    )
    export_stage.Save()

    # Use timer to chain operators together and properly refresh depsgraph
    bpy.app.timers.register(lambda: refresh_library_import(tmp_dir))


def refresh_library_import(tmp_dir: Path) -> None:
    """Remove all objects associated with a given library name"""
    library = bpy.context.scene.usd_connect_libraries[-1]

    old_objs = []
    for obj in bpy.context.scene.objects:
        if obj.usd_connect_props.library_name == library.name:
            obj.name = "OLD_" + obj.name
            old_objs.append(obj)

    with override_usd_session_state(active=True):
        import_usd_reference(library.ref_file_path, library.export_path)

    new_objs = [
        obj for obj in get_library_objects(library) if not obj.name.startswith("OLD_")
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

    shutil.rmtree(tmp_dir)


##############################################################
# Hook Core Operations
##############################################################
def hook_export_overrides(bl_stage: Usd.Stage, source_stage_path: str) -> None:
    library = bpy.context.scene.usd_connect_libraries[0]
    override_stage_path = library.export_path

    override_stage = Usd.Stage.CreateNew(override_stage_path)

    # Add reference to source stage in override file
    source_stage = Usd.Stage.Open(source_stage_path)

    override_stage.GetRootLayer().subLayerPaths.append(source_stage_path)

    generate_usd_overrides_for_prims(
        source_stage=source_stage,
        override_stage=override_stage,
        bl_stage=bl_stage,
    )

    # TODO Improve error handling on scaling when prim isn't found
    # BL_ROOT_PRIM = "/root"

    # world_override = override_stage.OverridePrim(
    #     "/" + library.root_prim_path.strip("/")
    # )
    # world_bl = bl_stage.GetPrimAtPath(BL_ROOT_PRIM + library.root_prim_path)

    # if world_bl.IsValid() and world_override.IsValid():
    #     apply_world_transform(world_bl, world_override)

    # root_override = override_stage.OverridePrim(BL_ROOT_PRIM)
    # root_bl = bl_stage.GetPrimAtPath(BL_ROOT_PRIM)

    # if root_bl.IsValid() and root_override.IsValid():
    #     apply_world_transform(root_bl, root_override)

    library.export_path = override_stage_path

    override_stage.Save()
    override_stage.Unload()


##############################################################################
# Prim Compare
##############################################################################

IGNORE_PROPS = [
    "userProperties:blender:object_name",
    "userProperties:blender:data_name",
]

def get_datablock_from_prim(blender_prim: Usd.Prim) -> dict:
    name = None

    if blender_prim.HasProperty("userProperties:blender:object_name"):
        name = blender_prim.GetProperty("userProperties:blender:object_name").Get()

    if blender_prim.HasProperty("userProperties:blender:data_name"):
        name = blender_prim.GetProperty("userProperties:blender:data_name").Get()

    if not name:
        return

    data_block_type = constants.get_datablock_type(blender_prim.GetTypeName())
    if data_block_type:
        return data_block_type.get(name)


def has_source_prim(blender_prim: Usd.Prim, source_stage: Usd.Stage) -> bool:
    """Check if the given Blender prim has a corresponding source prim in the source stage.

    Args:
        blender_prim (Usd.Prim): Prim Exported by Blender
        source_stage (Usd.Stage): Source USD Stage

    Returns:
        bool: True if the source prim exists, False otherwise
    """
    bl_data_block = get_datablock_from_prim(blender_prim)
    if bl_data_block and hasattr(bl_data_block, "usd_connect_props"):
        source_prim_path = bl_data_block.usd_connect_props.prim_path
        source_prim = source_stage.GetPrimAtPath(source_prim_path)
        if source_prim and source_prim.IsValid():
            return source_prim
    return False

def get_all_prims(stage:Usd.Stage) -> List[Usd.Prim]:
    """Get all prims in the stage, except for those autogenerated by Blender like "root".

    Args:
        stage (Usd.Stage): The USD stage to traverse.

    Returns:
        List[Usd.Prim]: A list of all non-generated prims in the stage.
    """
     # Filter out prims autogenerated by Blender like "root"
    all_prims : List[Usd.Prim] = []
    for bl_prim in stage.Traverse():
        if bl_prim.HasCustomDataKey("Blender"):
            if bl_prim.GetCustomDataByKey("Blender")["generated"] == True:
                continue
        all_prims.append(bl_prim)
    return all_prims


def get_matching_prims(source_stage:Usd.Stage, blender_prims:List[Usd.Prim]) -> dict[Usd.Prim, Usd.Prim]:
    """Get a mapping of matching prims between the source stage and Blender exported prims.

    Args:
        source_stage (Usd.Stage): The source USD stage to compare against.
        blender_prims (List[Usd.Prim]): The list of Blender exported prims.

    Returns:
        dict[Usd.Prim, Usd.Prim]: A mapping of matching prims between the source stage and Blender exported prims.
    """
    # Find all prims that match a path in the source stage
    matched_blender_prims: dict[Usd.Prim, Usd.Prim] = {}

    for bl_prim in blender_prims:
        # Find matching prim in source stage
        source_prim = has_source_prim(bl_prim, source_stage)
        if source_prim:
            matched_blender_prims[bl_prim] = source_prim

    return matched_blender_prims    


def get_unmatched_prims(blender_prims:List[Usd.Prim], matched_blender_prims:dict[Usd.Prim, Usd.Prim]) -> List[Usd.Prim]:
    """Get a list of unmatched Blender prims.

    Args:
        blender_prims (List[Usd.Prim]): List of Blender exported prims.
        matched_blender_prims (dict[Usd.Prim, Usd.Prim]): A mapping of matching prims between Blender exported prims as keys and source prim as values.

    Returns:
        List[Usd.Prim]: A list of unmatched Blender prims.
    """
    return list(set(blender_prims) - set(matched_blender_prims.keys()))


def generate_usd_overrides_for_prims(source_stage:Usd.Stage, override_stage:Usd.Stage, bl_stage:Usd.Stage) -> None:
    # Filter out prims autogenerated by Blender like "root"
    blender_prims = get_all_prims(bl_stage)

    # Collect all the relevant prims
    matched_prims = get_matching_prims(source_stage, blender_prims)
    unmatched_prims = get_unmatched_prims(blender_prims, matched_prims)

    # Figure out if prims have been modified
    for bl_prim, src_prim in matched_prims.items():
        PrimTransfer(bl_prim, src_prim, override_stage).generate_overrides()

    usd_connect_session = get_usd_connect_session()
    for unmatched in unmatched_prims:

        # During Refresh Skip anything that doesn't have a source prim set
        if usd_connect_session.refresh:
            if not unmatched.GetAttribute("userProperties:source_prm"):
                continue
            print(unmatched.GetPath())

        new_prim = override_stage.DefinePrim(
            unmatched.GetPath(), unmatched.GetTypeName()
        )
        try:
            Sdf.CopySpec(
                bl_stage.GetRootLayer(),
                unmatched.GetPath(),
                override_stage.GetRootLayer(),
                new_prim.GetPath(),
            )
            print(f"PRIM: Created New Prim: {new_prim.GetPath()}")
        except Exception as e:
            print(f"Error copying spec for new prim {unmatched.GetPath()}: {e}")


def apply_world_transform(source_prim: Usd.Prim, target_prim: Usd.Prim) -> None:

    source_xform = UsdGeom.Xformable(source_prim)
    target_xform = UsdGeom.Xformable(target_prim)

    # TODO support rotation

    if not target_xform.GetTranslateOp().IsDefined():
        target_xform.AddTranslateOp()

    if not target_xform.GetScaleOp().IsDefined():
        target_xform.AddScaleOp()

    world_transform_matrix = source_xform.ComputeLocalToWorldTransform(
        Usd.TimeCode.Default()
    )

    scale = Gf.Vec3f(
        world_transform_matrix.ExtractRotationMatrix().GetRow(0).GetLength(),
        world_transform_matrix.ExtractRotationMatrix().GetRow(1).GetLength(),
        world_transform_matrix.ExtractRotationMatrix().GetRow(2).GetLength(),
    )

    target_xform.GetTranslateOp().Set(world_transform_matrix.ExtractTranslation())

    # xformable_override.GetRotateXYZOp().Set(
    #     world_transform_matrix.ExtractRotationMatrix()
    # )

    target_xform.GetScaleOp().Set(scale)

##############################################################
# Helper Functions
##############################################################


def get_library_objects(library: bpy.types.Object) -> List[bpy.types.Object]:
    """Get all objects associated with a specific USD library."""
    return [
        obj
        for obj in bpy.context.scene.objects
        if obj.usd_connect_props.library_get() == library
    ]


def get_usd_connect_session() -> bpy.types.PropertyGroup:
    return bpy.context.window_manager.usd_connect_session


##############################################################
# Context Managers
##############################################################


@contextlib.contextmanager
def override_object_selection(objects: List[Object], view_layer: ViewLayer):
    object_states = {}
    for obj in objects:
        object_states[obj] = obj.select_get()

    try:
        for obj in objects:
            obj.select_set(True, view_layer=view_layer)
        yield
    finally:
        for obj in objects:
            obj.select_set(object_states[obj], view_layer=view_layer)


@contextlib.contextmanager
def override_usd_session_state(active: bool, refresh: bool = False):
    usd_connect_session = bpy.context.window_manager.usd_connect_session
    org_active = usd_connect_session.active
    org_refresh = usd_connect_session.refresh

    try:
        usd_connect_session.active = active
        usd_connect_session.refresh = refresh
        yield
    finally:
        usd_connect_session.active = org_active
        usd_connect_session.refresh = org_refresh


@contextlib.contextmanager
def override_library_filepaths(
    library: bpy.types.PropertyGroup, file_path: str, snapshot_path: str | None = None
):

    org_file_path = library.ref_file_path
    org_snapshot_path = library.snapshot_file_path

    try:
        library.ref_file_path = file_path
        if snapshot_path:
            library.snapshot_file_path = snapshot_path
        yield
    finally:
        library.ref_file_path = org_file_path
        if snapshot_path:
            library.snapshot_file_path = org_snapshot_path
