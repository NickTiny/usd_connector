import bpy

# TODO Verify all types that should be supported
# TODO Espcially cube, and other special types in USD

    
def get_datablock_type(prim_type:str) -> list[str]:
    prim_to_data_block_types = {
        "Mesh": bpy.data.meshes,
        "Xform": bpy.data.objects,
        "Camera": bpy.data.cameras,
        "Light": bpy.data.lights,
        "SphereLight": bpy.data.lights,
        "DistantLight": bpy.data.lights,
        "DiskLight": bpy.data.lights,
        "CylinderLight": bpy.data.lights,
        "RectLight": bpy.data.lights,
        "BasisCurves": bpy.data.curves,
        "NurbsCurves": bpy.data.curves,
        "Points": bpy.data.pointclouds,
        "Volume": bpy.data.volumes,
        "Material": bpy.data.materials
    }
    return prim_to_data_block_types.get(prim_type, None)