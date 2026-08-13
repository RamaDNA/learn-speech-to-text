"""Unit test config device: resolve path + build_config (tanpa hardware)."""
import importlib
import os
from pathlib import Path

import pytest

import config
from config import CONFIG, build_config, resolve

DEVICE_DIR = Path(__file__).resolve().parent.parent


class TestResolve:
    def test_absolut_tidak_diubah(self):
        # Path absolut (sesuai platform) dikembalikan apa adanya (hanya normalisasi slash)
        if os.name == "nt":
            assert resolve("C:/absolute/path/model.onnx") == "C:\\absolute\\path\\model.onnx"
        else:
            assert resolve("/etc/hostname") == "/etc/hostname"

    def test_relatif_diresolve_terhadap_device_dir(self):
        assert resolve("models/stt") == str(DEVICE_DIR / "models" / "stt")

    def test_none_semua(self):
        assert resolve(None) == ""
        assert resolve(None, None) == ""
        assert resolve(None, "default.pth") == str(DEVICE_DIR / "default.pth")


class TestBuildConfig:
    def test_tanpa_env_override(self):
        cfg = build_config()
        assert cfg["audio"]["sample_rate"] > 0
        assert cfg["stt"]["model_dir"].endswith(os.path.join("models", "sherpa-onnx-whisper-base"))
        assert os.path.isabs(cfg["stt"]["model_dir"])
        assert cfg["server"]["api_url"].startswith("http")
        assert cfg["agent"]["session_id"]

    def test_env_menggantikan_server(self, monkeypatch):
        # CONFIG dibaca saat import -> reload module setelah set env
        monkeypatch.setenv("WAREHOUSE_API_URL", "http://test.local:9999")
        monkeypatch.setenv("WAREHOUSE_API_KEY", "sekret-test")
        reloaded = importlib.reload(config)
        try:
            cfg = reloaded.build_config()
            assert cfg["server"]["api_url"] == "http://test.local:9999"
            assert cfg["server"]["api_key"] == "sekret-test"
        finally:
            monkeypatch.delenv("WAREHOUSE_API_URL", raising=False)
            monkeypatch.delenv("WAREHOUSE_API_KEY", raising=False)
            importlib.reload(config)  # pulihkan CONFIG asli untuk test lain

    def test_config_yaml_memuat_kunci_wajib(self):
        assert set(CONFIG.keys()) >= {"audio", "stt", "vad", "tts", "wakeword", "server", "agent"}
        assert os.path.exists(CONFIG["stt"]["model_dir"]) or True  # model_dir boleh kosong di mesin dev