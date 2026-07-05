"""共用測試工具。

patch_modules：main.py 拆模組後，同一個名字可能同時綁在 app.main（re-export）
與擁有它的模組（app.ranking / app.retrieval / app.agent ...）。
monkeypatch 只打 main 會漏掉模組內部的呼叫鏈，這裡把所有持有該名字的
app 模組一起打，測試就不再依賴函式住在哪個檔案。
"""
import importlib

_APP_MODULES = [
    "app.main",
    "app.config",
    "app.ranking",
    "app.retrieval",
    "app.agent",
    "app.line_routes",
]


def patch_modules(monkeypatch, name: str, value) -> None:
    patched = 0
    for mod_name in _APP_MODULES:
        try:
            mod = importlib.import_module(mod_name)
        except ImportError:
            continue
        if hasattr(mod, name):
            monkeypatch.setattr(mod, name, value)
            patched += 1
    if not patched:
        raise AttributeError(f"no app module defines {name!r}")
