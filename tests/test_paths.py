from src.config import paths


def test_cleanup_legacy_cache_paths_removes_only_known_old_cache_targets(tmp_path, monkeypatch):
    legacy_file = tmp_path / "otp_lol_ddragon_champions.json"
    legacy_dir = tmp_path / "otp_lol_icons"
    legacy_file.write_text("{}", encoding="utf-8")
    legacy_dir.mkdir()
    (legacy_dir / "garen.png").write_bytes(b"asset")

    monkeypatch.setattr(paths, "CACHE_ROOT", str(tmp_path / "new-cache"))
    monkeypatch.setattr(paths, "LEGACY_CACHE_PATHS", (str(legacy_file), str(legacy_dir)))

    paths.cleanup_legacy_cache_paths()

    assert not legacy_file.exists()
    assert not legacy_dir.exists()
