import os
import inspect
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import stype


class CoreBehaviorTests(unittest.TestCase):
    def test_resample_preserves_duration_and_float32(self):
        source = np.linspace(-0.5, 0.5, 48_000, dtype=np.float32)
        result = stype.resample_audio(source, 48_000, 16_000)
        self.assertEqual(result.dtype, np.float32)
        self.assertEqual(len(result), 16_000)
        self.assertAlmostEqual(float(result[0]), -0.5, places=3)

    def test_resample_matrix_is_finite_and_duration_safe(self):
        generator = np.random.default_rng(42)
        for source_rate in (8_000, 16_000, 44_100, 48_000):
            for duration in (0.01, 0.3, 2.0):
                source = generator.normal(0, 0.1, round(source_rate * duration)).astype(np.float32)
                result = stype.resample_audio(source, source_rate, 16_000)
                self.assertEqual(result.dtype, np.float32)
                self.assertEqual(len(result), round(16_000 * duration))
                self.assertTrue(np.isfinite(result).all())

    def test_post_process_applies_literal_case_insensitive_replacement(self):
        original = list(stype.data_manager.data.get("personal_dict", []))
        try:
            stype.data_manager.data["personal_dict"] = [
                {"target": "out words", "replacement": "outwards"}
            ]
            self.assertEqual(stype.post_process("move out words now"), "move outwards now.")
        finally:
            stype.data_manager.data["personal_dict"] = original

    def test_replacements_support_symbols_and_ignore_vocab_entries(self):
        original = list(stype.data_manager.data.get("personal_dict", []))
        try:
            stype.data_manager.data["personal_dict"] = [
                {"type": "replace", "target": "c++", "replacement": "C plus plus"},
                {"type": "vocab", "target": "Stype", "replacement": "wrong"},
            ]
            self.assertEqual(stype.post_process("Use C++ with Stype", "en"), "Use C plus plus with Stype.")
        finally:
            stype.data_manager.data["personal_dict"] = original

    def test_replacements_are_atomic_case_aware_and_path_safe(self):
        original = list(stype.data_manager.data.get("personal_dict", []))
        try:
            stype.data_manager.data["personal_dict"] = [
                {"type": "replace", "target": "iphone", "replacement": "iPhone"},
                {"type": "replace", "target": "alpha", "replacement": "beta"},
                {"type": "replace", "target": "beta", "replacement": r"C:\Users\Docs"},
            ]
            self.assertEqual(
                stype.post_process("iphone alpha beta", "hi"),
                r"iPhone beta C:\Users\Docs",
            )
        finally:
            stype.data_manager.data["personal_dict"] = original

    def test_non_english_transcription_is_never_translated_or_english_punctuated(self):
        options = stype.build_transcription_options("hi", ["स्टाइप"])
        self.assertEqual(options["task"], "transcribe")
        self.assertEqual(options["language"], "hi")
        self.assertTrue(options["multilingual"])
        self.assertNotIn("initial_prompt", options)
        self.assertEqual(stype.post_process("यह एक परीक्षण है", "hi"), "यह एक परीक्षण है")
        self.assertEqual(stype.compatible_model("small.en", "hi"), "large-v3-turbo")
        self.assertEqual(stype.compatible_model("small.en", "en"), "small.en")

    def test_every_language_uses_native_transcription(self):
        for language_code in stype.LANGUAGES.values():
            options = stype.build_transcription_options(language_code, [])
            self.assertEqual(options["task"], "transcribe")
            self.assertTrue(options["multilingual"])
            self.assertEqual(options["language"], language_code)

    def test_replacements_never_bias_recognition_as_hotwords(self):
        words = stype.dictionary_hotwords([
            {"type": "replace", "target": "wrong", "replacement": "right"},
            {"type": "vocab", "target": "Stype", "replacement": ""},
            {"type": "vocab", "target": "stype", "replacement": ""},
        ])
        self.assertEqual(words, ["Stype"])

    def test_engine_errors_are_actionable(self):
        self.assertIn("internet connection", stype.user_facing_engine_error("Connection timed out"))
        self.assertIn("Retry engine", stype.user_facing_engine_error("bad model.bin checksum"))

    def test_active_pill_renderer_is_flat_and_content_measured(self):
        source = inspect.getsource(stype.PillOverlay.paintEvent).casefold()
        implementation = "\n".join(source.splitlines()[2:])
        self.assertNotIn("shadow", implementation)
        self.assertNotIn("gradient", implementation)
        self.assertIn("fontmetrics", inspect.getsource(stype.PillOverlay.set_state).casefold())
        self.assertEqual(stype.PILL_READY_SIZE, (44, 24))
        self.assertLessEqual(stype.PILL_ACTIVE_SIZE[1], 26)

    def test_app_palette_matches_website_tokens(self):
        self.assertEqual(stype.NB_BG, "#FFFDF7")
        self.assertEqual(stype.NB_INK, "#1A1A2E")
        self.assertEqual(stype.NB_ORANGE, "#FF6B35")
        self.assertEqual(stype.NB_PURPLE, "#7B61FF")

    def test_pathological_repetition_and_morse_artifacts_are_removed(self):
        self.assertEqual(
            stype.collapse_transcription_loops("hello world hello world hello world next"),
            "hello world next",
        )
        self.assertEqual(stype.post_process("... --- ... --- ...", "en"), "")

    def test_repetition_filter_is_idempotent_across_phrase_widths(self):
        for width in range(1, 9):
            phrase = " ".join(f"word{index}" for index in range(width))
            original = f"{phrase} {phrase} {phrase} final"
            collapsed = stype.collapse_transcription_loops(original)
            self.assertEqual(collapsed, f"{phrase} final")
            self.assertEqual(stype.collapse_transcription_loops(collapsed), collapsed)

    def test_advanced_model_is_default_and_can_fall_back_to_download(self):
        self.assertEqual(stype.DEFAULT_MODEL_ID, "large-v3-turbo")
        path = stype.resolve_model_path(stype.DEFAULT_MODEL_ID)
        self.assertIsNotNone(path)
        self.assertTrue(os.path.isfile(os.path.join(path, "model.bin")))
        self.assertIsNone(stype.resolve_model_path(stype.DEFAULT_MODEL_ID, self.id(), self.id()))

    def test_downloaded_model_cache_is_resolved_without_network(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot = Path(temp_dir) / "models" / "models--Systran--faster-whisper-small.en" / "snapshots" / "abc"
            snapshot.mkdir(parents=True)
            for name in ("model.bin", "config.json", "tokenizer.json"):
                (snapshot / name).write_bytes(b"test")
            self.assertEqual(
                Path(stype.resolve_model_path("small.en", self.id(), temp_dir)),
                snapshot,
            )

    def test_single_instance_mutex_is_per_user(self):
        source = inspect.getsource(stype)
        self.assertIn(r'"Local\\StypeVoiceDictation_SingleInstance_v2"', source)
        self.assertNotIn(r'"Global\\StypeVoiceDictation_SingleInstance_v2"', source)

    def test_all_ui_states_have_labels_and_colors(self):
        for required in ("loading", "downloading", "ready", "listening", "processing", "pasted", "error"):
            self.assertIn(required, stype.STATES)
            self.assertTrue(stype.STATES[required]["label"])
            self.assertTrue(stype.STATES[required]["dot"].startswith("#"))

    def test_history_is_bounded_and_round_trips_unicode(self):
        original_file = stype.DATA_FILE
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = os.path.join(temp_dir, "stype_data.json")
            try:
                stype.DATA_FILE = test_file
                manager = stype.DataManager()
                for index in range(105):
                    manager.add_history(f"हिन्दी entry {index}")
                self.assertEqual(len(manager.data["history"]), 100)
                self.assertEqual(manager.data["history"][0]["text"], "हिन्दी entry 104")

                reloaded = stype.DataManager()
                self.assertEqual(reloaded.data["history"], manager.data["history"])
                with open(test_file, encoding="utf-8") as stream:
                    self.assertEqual(json.load(stream)["history"][0]["text"], "हिन्दी entry 104")
            finally:
                stype.DATA_FILE = original_file

    def test_microphone_inventory_filters_outputs_and_deduplicates(self):
        devices = [
            {"name": "USB Mic", "max_input_channels": 1, "hostapi": 0},
            {"name": "USB Mic 2 ()", "max_input_channels": 1, "hostapi": 1},
            {"name": "Speakers (Output)", "max_input_channels": 2, "hostapi": 0},
            {"name": "No Input", "max_input_channels": 0, "hostapi": 0},
        ]
        host_apis = [{"name": "Windows WASAPI"}, {"name": "MME"}]
        with mock.patch.object(stype.sd, "query_devices", return_value=devices), mock.patch.object(
            stype.sd, "query_hostapis", return_value=host_apis
        ):
            self.assertEqual(stype.get_input_devices(), [("USB Mic", 0, "Windows WASAPI")])

    def test_installer_removes_models_profile_and_startup_entry(self):
        script = (Path(__file__).parents[1] / "stype.iss").read_text(encoding="utf-8")
        normalized = script.casefold()
        self.assertIn("appversion=2.1.2", normalized)
        self.assertIn('[uninstalldelete]', normalized)
        self.assertIn('#define userdatadir "{userappdata}\\stype"', normalized)
        self.assertIn('type: filesandordirs; name: "{#userdatadir}"', normalized)
        self.assertIn('#define startupvaluename "stype"', normalized)
        self.assertIn('valuename: "{#startupvaluename}"; flags: dontcreatekey uninsdeletevalue', normalized)
        self.assertIn("closeapplications=yes", normalized)
        self.assertIn("restartapplications=no", normalized)
        self.assertIn("privilegesrequired=lowest", normalized)
        self.assertIn('name: "{userdesktop}\\stype"', normalized)


if __name__ == "__main__":
    unittest.main()
