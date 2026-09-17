import json
from pathlib import Path
import pytest

import secnorm
from secnorm.config import NormalizationConfig


def test_normalization_result_serialization_full():
    result = secnorm.normalize("  Ａｄｍｉｎ &amp; 배​포  ")
    d = result.to_dict(include_raw_text=True)

    assert isinstance(d, dict)
    assert d["raw_text"] == "  Ａｄｍｉｎ &amp; 배​포  "
    assert d["normalized_text"] == "Admin & 배포"
    assert isinstance(d["transformations"], list)
    assert isinstance(d["flags"], list)
    assert isinstance(d["language"], dict)
    assert isinstance(d["span_map"], dict)
    assert d["config_name"] == "security_balanced"

    # Verify json serialization
    json_str = result.to_json(include_raw_text=True, indent=2)
    parsed = json.loads(json_str)
    assert parsed["raw_text"] == d["raw_text"]
    assert parsed["normalized_text"] == d["normalized_text"]


def test_normalization_result_serialization_exclude_raw_text():
    result = secnorm.normalize("  Ａｄｍｉｎ &amp; 배​포  ")
    d = result.to_dict(include_raw_text=False)

    assert d["raw_text"] is None
    assert d["normalized_text"] == "Admin & 배포"

    json_str = result.to_json(include_raw_text=False)
    parsed = json.loads(json_str)
    assert parsed["raw_text"] is None
    assert parsed["normalized_text"] == "Admin & 배포"


def test_normalization_config_dict_and_json_roundtrip():
    cfg = NormalizationConfig()
    cfg.unicode.form = "NFC"
    cfg.invisible_control.strip_tag_chars = False
    cfg.whitespace.mode = "structural"
    cfg.invisible_control.preserve_whitelist.add("\r")

    d = cfg.to_dict()
    assert isinstance(d["enabled_steps"], list)
    assert isinstance(d["invisible_control"]["preserve_whitelist"], list)
    assert "\r" in d["invisible_control"]["preserve_whitelist"]

    # to_json and from_json
    json_str = cfg.to_json()
    loaded_cfg = NormalizationConfig.from_json(json_str)

    assert loaded_cfg.unicode.form == "NFC"
    assert loaded_cfg.invisible_control.strip_tag_chars is False
    assert loaded_cfg.whitespace.mode == "structural"
    assert "\r" in loaded_cfg.invisible_control.preserve_whitelist
    assert isinstance(loaded_cfg.enabled_steps, set)
    assert isinstance(loaded_cfg.invisible_control.preserve_whitelist, set)


def test_normalization_config_from_file(tmp_path: Path):
    cfg = NormalizationConfig()
    cfg.unicode.form = "NFD"

    # 1. JSON file
    json_file = tmp_path / "config.json"
    json_file.write_text(cfg.to_json(), encoding="utf-8")
    loaded_from_json = NormalizationConfig.from_file(json_file)
    assert loaded_from_json.unicode.form == "NFD"

    # 2. TOML file
    toml_content = """
    enabled_steps = ["unicode", "whitespace"]

    [unicode]
    form = "NFKD"

    [whitespace]
    mode = "structural"
    trim_edges = false
    """
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(toml_content, encoding="utf-8")
    loaded_from_toml = NormalizationConfig.from_file(toml_file)
    assert loaded_from_toml.enabled_steps == {"unicode", "whitespace"}
    assert loaded_from_toml.unicode.form == "NFKD"
    assert loaded_from_toml.whitespace.mode == "structural"
    assert loaded_from_toml.whitespace.trim_edges is False


def test_normalization_config_from_file_not_found():
    with pytest.raises(FileNotFoundError):
        NormalizationConfig.from_file("non_existent_path_xyz.json")
