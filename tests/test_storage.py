from pathlib import Path

from turnout import storage


class FakeStore:
    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def list(self, prefix):
        return {k: len(v) for k, v in self.objects.items() if k.startswith(prefix)}

    def upload(self, path: Path, key):
        self.objects[key] = path.read_bytes()

    def download(self, key, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.objects[key])


def test_push_uploads_only_new_or_changed_files(tmp_path):
    (tmp_path / "TXRH" / "2026-09-29").mkdir(parents=True)
    f = tmp_path / "TXRH" / "2026-09-29" / "ex99_1.txt"
    f.write_text("hello")
    store = FakeStore()
    assert storage.push(store, root=tmp_path) == 1
    assert storage.push(store, root=tmp_path) == 0  # nothing new
    f.write_text("hello, changed")
    assert storage.push(store, root=tmp_path) == 1
    assert "raw/TXRH/2026-09-29/ex99_1.txt" in store.objects


def test_pull_downloads_selected_tickers(tmp_path):
    store = FakeStore()
    store.objects = {"raw/TXRH/q/a.txt": b"a", "raw/WMT/q/b.txt": b"b"}
    assert storage.pull(store, ["TXRH"], root=tmp_path) == 1
    assert (tmp_path / "TXRH" / "q" / "a.txt").read_text() == "a"
    assert not (tmp_path / "WMT").exists()
    assert storage.pull(store, None, root=tmp_path) == 1  # only WMT is new
