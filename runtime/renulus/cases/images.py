# SPDX-License-Identifier: MIT
"""Read-only selected-account image gates; bytes use the runtime validator."""
from renulus.contracts import ApiError
from renulus.runtime.inputs import MAX_IMAGE_BYTES, MAX_IMAGE_PIXELS
from renulus.runtime.policy import ALLOWED_MODELS, require_learning_route


def image_capabilities(services):
    models = []
    selected = None
    code = 'image_capabilities_unverified'
    reason = 'The selected account has no verified image-input model. Check Connections.'
    retryable = True
    try:
        status = services.get('provider').connections()
        selected = status['selected_provider']
        require_learning_route(selected)
        row = next(row for row in status['connections'] if row['provider'] == selected)
        if row['status'] == 'connected':
            models = [item['id'] for item in row['models']
                      if item['id'] in ALLOWED_MODELS[selected]
                      and item['availability'] == 'available' and item['image_input'] == 'supported']
    except ApiError as error:
        models = []
        if error.code == 'learning_use_unverified':
            code, reason, retryable = error.code, error.message, error.retryable
    except Exception:
        models = []
    return {'supported': bool(models), 'models': models, 'provider': selected,
            'interpretation_verified': False, 'max_bytes': MAX_IMAGE_BYTES,
            'image_pixels': MAX_IMAGE_PIXELS, 'formats': ['.png', '.jpg', '.jpeg'],
            'code': None if models else code, 'reason': None if models else reason,
            'retryable': False if models else retryable,
            'retention': 'Image bytes are temporary and omitted from Save; text and completed discussion require explicit Save.'}


def require_image_model(services, model):
    result = image_capabilities(services)
    if model not in result['models']:
        code = result['code'] or 'image_capabilities_unverified'
        raise ApiError(code, result['reason'] or 'The selected image model is unavailable',
                       403 if code == 'learning_use_unverified' else 409, result['retryable'])
    return result
