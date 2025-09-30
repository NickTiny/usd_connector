
from typing import Any

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