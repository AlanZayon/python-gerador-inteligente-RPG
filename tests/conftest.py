import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_redis():
    store = {}

    conn = MagicMock()

    def hset(key, mapping=None, **kwargs):
        m = mapping or kwargs.get("mapping") or {}
        store.setdefault(key, {})
        store[key].update(m)

    def hgetall(key):
        return store.get(key, {})

    def expire(key, ttl):
        pass

    conn.hset = hset
    conn.hgetall = hgetall
    conn.expire = expire
    conn.data = store
    return conn
