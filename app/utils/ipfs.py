import os

from ..models.url_types import IPFSURL, create_url_object


class IPFSAccessError(RuntimeError):
    """Raised when an IPFS/IPNS source cannot be read through local Kubo."""


def get_fetch_url(url):
    """Return a local Kubo gateway URL for IPFS/IPNS sources."""
    url_obj = create_url_object(url)
    if not isinstance(url_obj, IPFSURL):
        return url

    if os.environ.get('ENABLE_IPFS', 'false').lower() != 'true':
        raise IPFSAccessError(
            'This IPFS/IPNS source requires Kubo. Enable it with ENABLE_IPFS=true.'
        )

    return url_obj.get_local_gateway_url()
