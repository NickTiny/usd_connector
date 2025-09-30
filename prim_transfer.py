from pxr import Usd
from typing import Dict, Any, Optional
from .utils import compare_usd_values

IGNORE_PROPS = [
    "userProperties:blender:object_name",
    "userProperties:blender:data_name",
]


class PrimTransfer:
    """
    NOTE: This class assumes, bl_stage, source_stage and target_stage are all active in memory.
    It also assumes that target_stage has the source_stage as a sublayer.
    """

    def __init__(
        self, bl_prim: Usd.Prim, source_prim: Usd.Prim, target_stage: Usd.Stage
    ) -> None:
        self.bl_prim: Usd.Prim = bl_prim
        self.source_prim: Usd.Prim = source_prim
        self.target_stage: Usd.Stage = target_stage

    def get_property_value(self, prop: Usd.Property) -> Optional[Any]:
        """Get the value from a property, handling both Get() and GetTargets() methods."""
        if hasattr(prop, "GetTargets"):
            return prop.GetTargets()
        elif hasattr(prop, "Get"):
            return prop.Get()
        return None

    def set_property_value(self, prop: Usd.Property, value: Any) -> None:
        """Set the value on a property, handling both Set() and SetTargets() methods."""
        if hasattr(prop, "SetTargets"):
            prop.SetTargets(value)
        elif hasattr(prop, "Set"):
            prop.Set(value)

    def compare_prim_properties(
        self, src_prim: Usd.Prim, trg_prim: Usd.Prim
    ) -> Dict[str, Any]:
        """Compare properties between two prims and return dictionary of differences."""
        differences = {}

        for trg_prop in trg_prim.GetProperties():
            if trg_prop.GetName() in IGNORE_PROPS:
                continue

            src_prop = src_prim.GetProperty(trg_prop.GetName())
            trg_value = self.get_property_value(trg_prop)
            
            if trg_value is None:
                continue

            if not src_prop:
                # Property missing in source, add it
                differences[trg_prop.GetName()] = trg_value
                continue

            # Compare existing properties
            src_value = self.get_property_value(src_prop)
            if not compare_usd_values(src_value, trg_value):
                differences[trg_prop.GetName()] = trg_value

        return differences

    def apply_property_overrides(
        self,
        src_prim: Usd.Prim,
        override_stage: Usd.Stage,
        property_differences: Dict[str, Any],
    ) -> None:
        """Apply property differences as overrides to the override stage."""
        override_prim = self.get_override_prim(src_prim, override_stage)
        if not override_prim:
            return

        for prop_name, prop_value in property_differences.items():
            override_prop = override_prim.GetProperty(prop_name)
            self.set_property_value(override_prop, prop_value)
            print(f"PROP: Overrided '{prop_name}' on '{src_prim.GetPath()}'")

    def generate_overrides(self) -> None:
        """Generate overrides on the target stage for differences between bl_prim and source_prim."""
        differences = self.compare_prim_properties(self.source_prim, self.bl_prim)
        self.apply_property_overrides(self.source_prim, self.target_stage, differences)

    def get_changes(self) -> Dict[str, Any]:
        """Get the property differences between bl_prim and source_prim."""
        return self.compare_prim_properties(self.source_prim, self.bl_prim)
    
    def get_override_prim(self, src_prim: Usd.Prim, override_stage: Usd.Stage) -> Usd.Prim:
        try:
            override_prim = override_stage.OverridePrim(src_prim.GetPath())
        except Exception as e:
            print(f"Error getting override prim: {e}")
            return
        print(f"PRIM: Overriding Prim: {src_prim.GetPath()}")
        return override_prim

