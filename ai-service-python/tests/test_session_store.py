import redis

import app.session_store as session_store


class BrokenRedis:
    def get(self, key):
        raise redis.ConnectionError("redis unavailable")

    def setex(self, key, ttl, value):
        raise redis.ConnectionError("redis unavailable")

    def delete(self, key):
        raise redis.ConnectionError("redis unavailable")


def test_session_store_falls_back_to_memory_when_redis_is_unavailable(monkeypatch):
    monkeypatch.setattr(session_store, "_client", BrokenRedis())
    session_store.clear_session("fallback-test")

    session_store.save_history(
        "fallback-test",
        [
            {"role": "user", "content": "推薦信義區火鍋"},
            {"role": "model", "content": "我整理了三間。"},
        ],
    )

    assert session_store.load_history("fallback-test") == [
        {"role": "user", "content": "推薦信義區火鍋"},
        {"role": "model", "content": "我整理了三間。"},
    ]

    session_store.clear_session("fallback-test")
    assert session_store.load_history("fallback-test") == []
