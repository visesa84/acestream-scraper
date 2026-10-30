import os
import asyncio
import unittest
from unittest.mock import patch

from app.models.url_types import IPFSURL, RegularURL, create_url_object
from app.services.m3u_service import M3UService
from app.utils.ipfs import get_fetch_url


class IPFSURLTests(unittest.TestCase):
    def test_ipns_subdomain_gateway_uses_local_kubo(self):
        source = (
            'https://k51qzi5uqu5dh5qej4b9wlcr5i6vhc7rcfkekhrxqek5c9lk6gdaiik820fecs'
            '.ipns.inbrowser.link/'
        )

        url_obj = create_url_object(source, 'regular')

        self.assertIsInstance(url_obj, IPFSURL)
        self.assertEqual(
            url_obj.get_local_gateway_url(),
            'http://127.0.0.1:8080/ipns/'
            'k51qzi5uqu5dh5qej4b9wlcr5i6vhc7rcfkekhrxqek5c9lk6gdaiik820fecs/'
        )
        self.assertEqual(url_obj.original_url, source)

    def test_dnslink_ipns_subdomain_preserves_dotted_name(self):
        source = 'https://en.example.test.ipns.dweb.link/'

        self.assertEqual(
            IPFSURL(source).get_local_gateway_url(),
            'http://127.0.0.1:8080/ipns/en.example.test/'
        )

    def test_ipfs_subdomain_preserves_path_and_query(self):
        source = 'https://bafybeigdyrzt.ipfs.dweb.link/lists/channels.m3u?token=a'

        self.assertEqual(
            IPFSURL(source).get_local_gateway_url(),
            'http://127.0.0.1:8080/ipfs/bafybeigdyrzt/lists/channels.m3u?token=a'
        )

    def test_root_relative_m3u_link_keeps_ipfs_resource(self):
        service = M3UService()

        urls = asyncio.run(service.find_m3u_links(
            '<a href="/lists/channels.m3u">',
            'http://127.0.0.1:8080/ipns/example.test/subpage'
        ))

        self.assertIn(
            'http://127.0.0.1:8080/ipns/example.test/lists/channels.m3u',
            urls
        )

    def test_native_ipns_and_path_gateway_urls_are_supported(self):
        self.assertEqual(
            IPFSURL('ipns://example.test/live/list.m3u').get_local_gateway_url(),
            'http://127.0.0.1:8080/ipns/example.test/live/list.m3u'
        )
        self.assertEqual(
            IPFSURL('https://ipfs.io/ipfs/bafybeigdyrzt/list.m3u').get_local_gateway_url(),
            'http://127.0.0.1:8080/ipfs/bafybeigdyrzt/list.m3u'
        )

    def test_non_ipfs_http_url_remains_regular(self):
        self.assertIsInstance(
            create_url_object('https://example.com/list.m3u'),
            RegularURL
        )

    def test_ipfs_fetch_requires_kubo_to_be_enabled(self):
        with patch.dict(os.environ, {'ENABLE_IPFS': 'false'}):
            with self.assertRaisesRegex(RuntimeError, 'ENABLE_IPFS=true'):
                get_fetch_url('ipfs://bafybeigdyrzt/list.m3u')

    def test_ipfs_fetch_uses_local_gateway_when_kubo_is_enabled(self):
        with patch.dict(os.environ, {'ENABLE_IPFS': 'true'}):
            self.assertEqual(
                get_fetch_url('ipfs://bafybeigdyrzt/list.m3u'),
                'http://127.0.0.1:8080/ipfs/bafybeigdyrzt/list.m3u'
            )


if __name__ == '__main__':
    unittest.main()
