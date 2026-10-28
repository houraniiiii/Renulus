# SPDX-License-Identifier: MIT
"""Read-only pack validation over the host's bounded file snapshot."""
import base64
import binascii
import json

from renulus.content.validation import PackValidationError, _unique_pairs, validate_pack
from .artifacts import Refused


def validate_content(body):
    try:
        encoded = json.loads(body, object_pairs_hook=_unique_pairs)
        if not isinstance(encoded, dict) or not 1 <= len(encoded) <= 128:
            raise PackValidationError('Invalid pack snapshot')
        files = {name: base64.b64decode(value, validate=True) for name, value in encoded.items()}
        pack = validate_pack(files)
    except (PackValidationError, ValueError, TypeError, binascii.Error):
        raise Refused('invalid_content_pack') from None
    return {'manifest': pack.manifest, 'sha256': pack.sha256,
            'bundle': {name: pack.bundle[name] for name in ('topics', 'cases', 'questions', 'sources')}}
