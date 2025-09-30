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


###############################################################
# Export / Import Operations
###############################################################
def import_usd_reference(filepath, stage_filepath=None):
    """Import a USD reference file and set up the library and prim mappings.

    NOTE: Must be called with hook registered, similar to direct operator call"""
    if not stage_filepath:
        stage_filepath = filepath

    source_file = Path(filepath)
    libraries = bpy.context.scene.usd_connect_libraries

    # TODO Due to exporter limitations we only support one library for now
    libraries.clear()
    library = libraries.add()

    # Setup Basic Library Info
    library.name = source_file.name
    library.file_path = filepath

    # Set Snapshot Path
    snapshot_dir = source_file.parent.joinpath("usd_snapshots")
    library.file_path_snapshot = snapshot_dir.joinpath(
        "snapshot_" + source_file.name
    ).as_posix()

    # Set Export Path
    library.export_path = source_file.parent.joinpath(
        "layer_" + source_file.name
    ).as_posix()

    bpy.ops.wm.usd_import("EXEC_DEFAULT", filepath=stage_filepath)

    bpy.app.timers.register(import_create_usd_snapshot, first_interval=1.0)


def export_usd_layer(
    target_filepath: Path, selected_objects_only: bool = False
) -> None:
    """Export the current scene to a USD file and generate overrides for the current library.

    NOTE: Must be called with hook registered, similar to direct operator call"""

    library = bpy.context.scene.usd_connect_libraries[0]

    # Store Actual Export Path in Library
    library.export_path = target_filepath.as_posix()

    # Pass Temp Path to Operator, to generate full USD file first
    # Hook will execute to generate override file at target filepath
    tmp_filepath = target_filepath.parent.joinpath("tmp_" + target_filepath.name)

    bpy.ops.wm.usd_export(
        filepath=tmp_filepath.as_posix(),
        selected_objects_only=selected_objects_only,
    )

    # Delete Temp File after Layer is generated
    if tmp_filepath.exists():
        tmp_filepath.unlink()


def import_create_usd_snapshot():
    library = bpy.context.scene.usd_connect_libraries[-1]
    shutil.copy(library.file_path, library.file_path_snapshot)


##############################################################
# Refresh Functions
##############################################################


def refresh_export_usd_layer() -> None:
    """Import a USD reference file and set up the library and prim mappings.

    Args:
        source_filepath (str): The file path of the source USD file to be used for overriding.
        file_to_load (str | None, optional): Override the USD file to load. Defaults to None.
    """
    library = bpy.context.scene.usd_connect_libraries[0]

    library_objects = get_library_objects(library)

    workspace = Path(library.file_path).parent
    export_path = workspace.joinpath("refresh_export.usda")

    old_filepath = library.file_path
    library.file_path = library.file_path_snapshot

    with override_object_selection(
        objects=library_objects, view_layer=bpy.context.view_layer
    ):
        export_usd_layer(export_path, selected_objects_only=True)
    library.file_path = old_filepath

    export_stage = Usd.Stage.Open(export_path.as_posix())
    export_stage.GetRootLayer().subLayerPaths.replace(
        library.file_path_snapshot, old_filepath
    )
    export_stage.Save()


def refresh_library_import() -> None:
    """Remove all objects associated with a given library name"""
    library = bpy.context.scene.usd_connect_libraries[-1]

    old_objs = []
    for obj in bpy.context.scene.objects:
        if obj.usd_connect_props.library_name == library.name:
            obj.name = "OLD_" + obj.name
            old_objs.append(obj)

    with override_usd_session_state(active=True):
        import_usd_reference(library.file_path, library.export_path)

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

def get_override_prim(src_prim: Usd.Prim, override_stage: Usd.Stage) -> Usd.Prim:
    try:
        override_prim = override_stage.OverridePrim(src_prim.GetPath())
    except Exception as e:
        print(f"Error getting override prim: {e}")
        return
    print(f"PRIM: Overriding Prim: {src_prim.GetPath()}")
    return override_prim


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


def compare_usd_values(value1: Any, value2: Any, precision: int = 2) -> bool:
    """Compare two USD values with customizable precision for floating point numbers.

    This function handles various USD types including Vec3d, Vec3f, Vec2d, Vec2f,
    matrices, quaternions, and other numerical types, rounding them to the specified
    precision before comparison.

    Args:
        value1 (Any): First value to compare
        value2 (Any): Second value to compare
        precision (int): Number of decimal places to round to for floating point comparisons

    Returns:
        bool: True if values are equal (within precision), False otherwise
    """
    if value1 is None and value2 is None:
        return True
    if value1 is None or value2 is None:
        return False

    # Handle different USD types
    if type(value1) != type(value2):
        return False

    if value1 == value2:
        return True

    # USD Array types (Vt.Vec3fArray, Vt.FloatArray, etc.)
    if hasattr(value1, '__class__') and 'Array' in str(type(value1)):
        try:
            if len(value1) != len(value2):
                return False
            for i in range(len(value1)):
                if not compare_usd_values(value1[i], value2[i], precision):
                    return False
            return True
        except (TypeError, IndexError, AttributeError):
            pass

    # Vector types (Vec3d, Vec3f, Vec2d, Vec2f, etc.)
    if hasattr(value1, '__len__') and hasattr(value1, '__getitem__'):
        try:
            if len(value1) != len(value2):
                return False
            for i in range(len(value1)):
                if isinstance(value1[i], (float, int)):
                    if round(float(value1[i]), precision) != round(
                        float(value2[i]), precision
                    ):
                        return False
                else:
                    if value1[i] != value2[i]:
                        return False
            return True
        except (TypeError, IndexError):
            pass

    # Matrix types (GfMatrix4d, GfMatrix3d, etc.)
    if hasattr(value1, 'GetRow') and hasattr(value1, 'GetNumRows'):
        try:
            if value1.GetNumRows() != value2.GetNumRows():
                return False
            for row in range(value1.GetNumRows()):
                if not compare_usd_values(
                    value1.GetRow(row), value2.GetRow(row), precision
                ):
                    return False
            return True
        except (TypeError, AttributeError):
            pass

    # Quaternion types
    if hasattr(value1, 'GetReal') and hasattr(value1, 'GetImaginary'):
        try:
            real_equal = round(float(value1.GetReal()), precision) == round(
                float(value2.GetReal()), precision
            )
            imag_equal = compare_usd_values(
                value1.GetImaginary(), value2.GetImaginary(), precision
            )
            return real_equal and imag_equal
        except (TypeError, AttributeError):
            pass

    # Single floating point numbers
    if isinstance(value1, (float, int)) and isinstance(value2, (float, int)):
        return round(float(value1), precision) == round(float(value2), precision)

    # Fallback to direct comparison for other types (strings, bools, etc.)
    return value1 == value2


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


def override_property(
    src_prim: Usd.Prim, trg_prop: Usd.Property, override_stage: Usd.Stage
):
    if trg_prop.GetName() in IGNORE_PROPS:
        return
    src_prop = src_prim.GetProperty(trg_prop.GetName())

    if not src_prop:
        print(f"PROP: Missing '{trg_prop.GetName()}' on '{src_prim.GetPath()}'")
        return

    if hasattr(src_prop, "GetTargets"):
        if trg_prop.GetTargets() is None:
            print(
                f"PROP: Targets None '{trg_prop.GetName()}' on '{src_prim.GetPath()}'"
            )
            return
        # Special Property Handling
        if not compare_usd_values(src_prop.GetTargets(), trg_prop.GetTargets()):
            override_prim = get_override_prim(src_prim, override_stage)
            if not override_prim:
                return
            override_prim.GetProperty(trg_prop.GetName()).SetTargets(
                trg_prop.GetTargets()
            )
            print(f"PROP: Overrided  '{trg_prop.GetName()}' on '{src_prim.GetPath()}'")
            return

    # Skip attributes that don't have get (relationships AFAIK)
    if hasattr(trg_prop, "Get"):
        if trg_prop.Get() is None:
            print(
                f"PROP: Targets None '{trg_prop.GetName()}' on '{src_prim.GetPath()}'"
            )
            return
        if not compare_usd_values(src_prop.Get(), trg_prop.Get()):
            override_prim = get_override_prim(src_prim, override_stage)
            if not override_prim:
                return
            override_prim.GetProperty(trg_prop.GetName()).Set(trg_prop.Get())
            print(f"PROP: Overrided '{trg_prop.GetName()}' on '{src_prim.GetPath()}'")
            return


def override_attribute(
    src_prim: Usd.Prim,
    trg_attr: Usd.Attribute,
    override_stage: Usd.Stage,
):

    if trg_attr.GetName() in IGNORE_PROPS:
        return
    if trg_attr.Get() is None:
        print(f"ATTR: Targets None '{trg_attr.GetName()}' on '{src_prim.GetPath()}'")
        return

    if src_prim.HasAttribute(trg_attr.GetName()):
        src_value = src_prim.GetAttribute(trg_attr.GetName()).Get()
        trg_value = trg_attr.Get()

        if not compare_usd_values(src_value, trg_value):
            override_prim = get_override_prim(src_prim, override_stage)
            if not override_prim:
                return
            override_prim.GetAttribute(trg_attr.GetName()).Set(trg_attr.Get())
            print(f"ATTR: Overrided '{trg_attr.GetName()}' on '{src_prim.GetPath()}'")
    else:
        override_prim = get_override_prim(src_prim, override_stage)
        if not override_prim:
            return
        # Attribute doesn't exist on source prim, add it
        override_prim.CreateAttribute(trg_attr.GetName(), trg_attr.GetTypeName()).Set(
            trg_attr.Get()
        )
        print(f"ATTR: Created '{trg_attr.GetName()}' on '{src_prim.GetPath()}'")


def override_prim_attributes_and_properties(
    blender_prim: Usd.Prim, source_prim: Usd.Prim, override_stage: Usd.Stage
) -> None:
    """Override the attribute of a prim in the override stage if it differs from the source stage.

    Args:
        blender_prim (Usd.Prim): The Blender exported prim.
        source_prim (Usd.Prim): The source prim to compare against.
        override_stage (Usd.Stage): The override stage to apply changes to.
    """
    # TODO Handle in a more generic way and support other attributes
    # This is good for demo purposes, but not a general solution

    for bl_attr in blender_prim.GetAttributes():
        override_attribute(source_prim, bl_attr, override_stage)

    for bl_prop in blender_prim.GetProperties():
        # If Property exists on source prim and value is different, override it
        override_property(source_prim, bl_prop, override_stage)


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
        # check_matching_prims(bl_prim, src_prim)
        override_prim_attributes_and_properties(bl_prim, src_prim, override_stage)

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
        print(f"PRIM: Created New Prim: {new_prim.GetPath()}")
        Sdf.CopySpec(
            bl_stage.GetRootLayer(),
            unmatched.GetPath(),
            override_stage.GetRootLayer(),
            new_prim.GetPath(),
        )


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
