"""The proxy must forward wire bytes with their original content encoding."""
import gzip
import zlib
import httpx
import pytest
from app import main, tools_proxy
from app.db import SessionLocal
from app.models import User
from sqlalchemy import select
from app.security import encrypt
from test_portal import setup


class WireStream(httpx.AsyncByteStream):
    def __init__(self, body):
        self.body = body
        self.closed = False

    async def __aiter__(self):
        for offset in range(0, len(self.body), 7):
            yield self.body[offset:offset + 7]

    async def aclose(self):
        self.closed = True


@pytest.mark.parametrize('encoding', ['identity', 'gzip', 'deflate', 'gzip, deflate', 'vendor-compression'])
@pytest.mark.parametrize('asset,content_type', [('', 'text/html'), ('app.js', 'application/javascript'), ('logo.png', 'image/png')])
def test_native_response_preserves_wire_encoding(client, monkeypatch, encoding, asset, content_type):
    setup(client)
    with SessionLocal() as db:
        for name, value in {'radarr_enabled': 'true', 'radarr_url': 'http://radarr.private:7878', 'radarr_api_key': encrypt('private-key')}.items():
            main.set_config(db, name, value)
        db.scalar(select(User).where(User.admin.is_(True))).tool_access='["radarr"]'
        db.commit()
    plain = b'<html><body>Radarr UI</body></html>' if not asset else (b'window.loaded=true;' if asset.endswith('.js') else b'\x89PNG\r\n\x1a\n\x00\xff\x80')
    wire = gzip.compress(plain) if encoding == 'gzip' else zlib.compress(plain) if encoding == 'deflate' else zlib.compress(gzip.compress(plain)) if encoding == 'gzip, deflate' else plain
    # Unknown encodings model formats unavailable in Gatearr's HTTP client;
    # they must still reach the browser intact with their encoding metadata.
    if encoding == 'vendor-compression':
        wire = b'\x00\xff\x80opaque-compressed-payload'
    stream = WireStream(wire)
    original = httpx.AsyncClient

    async def upstream(request):
        assert request.headers['accept-encoding'] == 'identity'
        assert request.headers['x-api-key'] == 'private-key'
        # A native service can ignore identity, e.g. for precompressed assets.
        return httpx.Response(200, stream=stream, headers={
            'Content-Type': content_type, 'Content-Encoding': encoding,
            'Content-Length': str(len(wire)), 'Set-Cookie': 'native=secret',
        })

    monkeypatch.setattr(tools_proxy.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(upstream), **kw))
    result = client.get('/tools/radarr/app/' + asset)
    assert result.status_code == 200
    assert result.headers.get('content-encoding') == encoding
    assert result.headers['content-type'] == content_type
    assert result.content == (wire if encoding == 'vendor-compression' else plain)
    assert 'set-cookie' not in result.headers
    assert 'content-length' not in result.headers
    assert stream.closed


@pytest.mark.parametrize('encoding,compressed_hex', [
    ('br', '1b2200f8c56d6c5dd7887e37882f341a75a4a2459ffa04186cfed6f3249b122a04'),
    ('zstd', '28b52ffd20231901003c68746d6c3e3c626f64793e5261646172722055493c2f626f64793e3c2f68746d6c3e'),
])
def test_native_precompressed_html_without_optional_decoders(client, monkeypatch, encoding, compressed_hex):
    # Real Brotli/Zstandard encodings of <html><body>Radarr UI</body></html>,
    # generated with Node's built-in zlib. No optional decompressor is required.
    from httpx._decoders import SUPPORTED_DECODERS
    monkeypatch.delitem(SUPPORTED_DECODERS, encoding, raising=False)
    setup(client)
    with SessionLocal() as db:
        for name, value in {'radarr_enabled': 'true', 'radarr_url': 'http://radarr.private:7878', 'radarr_api_key': encrypt('private-key')}.items():
            main.set_config(db, name, value)
        db.scalar(select(User).where(User.admin.is_(True))).tool_access='["radarr"]'
        db.commit()
    wire = bytes.fromhex(compressed_hex)
    stream = WireStream(wire)
    original = httpx.AsyncClient

    async def upstream(request):
        assert request.headers.get_list('accept-encoding') == ['identity']
        return httpx.Response(200, stream=stream, headers={'Content-Type': 'text/html', 'Content-Encoding': encoding})

    monkeypatch.setattr(tools_proxy.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(upstream), **kw))
    result = client.get('/tools/radarr/app/', headers={'Accept-Encoding': 'gzip, deflate, br, zstd'})
    assert result.status_code == 200 and result.headers['content-encoding'] == encoding
    assert result.content == wire and stream.closed
