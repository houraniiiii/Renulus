# SPDX-License-Identifier: MIT
"""Reference-only source coordinates shared by Library and answer receipts.

This checks the retained provenance shape, not source eligibility or reader
mapping. Those remain with their canonical owners. It never reads source bytes.
"""
import math


_GEOMETRY = {"l": (int, float), "t": (int, float), "r": (int, float),
    "b": (int, float), "coord_origin": str}
_SIZE = {"width": (int, float), "height": (int, float)}
_CONTENT_LOCATION = {"kind": str, "item_ref": str, "section": str, "start": int, "end": int,
    "format": str, "sheet_name": str, "first_row": int, "last_row": int,
    "first_column": int, "last_column": int, "physical_page": int, "printed_label": str,
    "frame": int, "bounds": [(int, float)]}
_SOURCE_LOCATION = {"item_ref": str, "table_ref": str, "page": int, "char_span": [int],
    "bbox": _GEOMETRY, "page_size": _SIZE, "format": str, "slide": int, "slide_size": _SIZE,
    "sheet": int, "sheet_name": str, "cell_bbox": _GEOMETRY, "content_locator": _CONTENT_LOCATION}


def _reference_shape(value, shape):
    if value is None:
        return True
    if isinstance(shape, dict):
        return (isinstance(value, dict) and not set(value) - shape.keys()
            and all(_reference_shape(item, shape[key]) for key, item in value.items()))
    if isinstance(shape, list):
        return isinstance(value, list) and all(_reference_shape(item, shape[0]) for item in value)
    if type(value) is float and not math.isfinite(value):
        return False
    return type(value) in shape if isinstance(shape, tuple) else type(value) is shape


def valid_source_provenance(locators):
    """Admit bounded raw coordinates without bodies, paths or arbitrary fields.

    The enclosing receipt applies its own serialized byte budget. Nullable
    coordinates and raw format-specific identities are retained without guessed
    reader offsets or normalization.
    """
    return (isinstance(locators, list) and len(locators) <= 12000
        and all(isinstance(location, dict) and _reference_shape(location, _SOURCE_LOCATION)
            for location in locators))
