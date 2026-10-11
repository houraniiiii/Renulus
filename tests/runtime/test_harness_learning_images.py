"""Actual image parser behind admitted saved learning callback authority."""
import pytest

from renulus.contracts import ApiError
from renulus.runtime.harness_domain import DomainCancellation, DomainRequest
from tests.runtime.test_harness_learning_current import saved_callback


PNG = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAAAAAA6fptVAAAACklEQVR4nGNgAAAAAgABSK+kcQAAAABJRU5ErkJggg=='


async def test_admitted_saved_image_callback_decodes_exact_inline_bytes(saved_callback):
    _, _, repo, _ = saved_callback
    owner = repo.services.registry['harness_learning']
    binding = owner.bridge.transport.binding
    request = DomainRequest('synthetic-image-decoder', binding, 'learning.validate_images',
        {'images': [{'type': 'image', 'media_type': 'image/png', 'data': PNG}]})
    grant = await owner.authorize(request)
    assert grant is not None and grant.check_current() is True
    assert await grant.handler(request, DomainCancellation()) == {'validated': True}


@pytest.mark.parametrize('images', [
    [{'type': 'image', 'media_type': 'image/jpeg', 'data': PNG}],
    [{'type': 'image', 'media_type': 'image/png', 'data': 'PRIVATE_SYNTHETIC_INVALID_IMAGE'}],
])
async def test_admitted_saved_image_callback_rejects_format_or_bytes_without_echoing_them(saved_callback, images):
    _, _, repo, _ = saved_callback
    owner = repo.services.registry['harness_learning']
    request = DomainRequest('synthetic-invalid-image', owner.bridge.transport.binding,
        'learning.validate_images', {'images': images})
    grant = await owner.authorize(request)
    assert grant is not None
    with pytest.raises(ApiError) as refused:
        await grant.handler(request, DomainCancellation())
    assert refused.value.code == 'invalid_image'
    assert images[0]['data'] not in refused.value.message
