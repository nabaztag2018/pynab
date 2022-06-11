import os
import platform
import sys
import unittest

import pytest

from nabd.asr import ASR


@pytest.mark.skipif(
    "CI" in os.environ
    and sys.platform == "linux"
    and "x86_64" in platform.machine(),
    reason="Kaldi currently crashes in GitHub CI",
)
class TestASR(unittest.TestCase):
    def test_get_model(self):
        self.assertEqual("fr_FR", ASR.get_locale("fr_FR"))
        self.assertEqual("en_GB", ASR.get_locale("en_GB"))
        self.assertEqual("en_US", ASR.get_locale("en_US"))
        self.assertEqual("fr_FR", ASR.get_locale("de_DE"))

    def test_load_model_fr(self):
        asr = ASR("fr_FR")
        self.assertTrue(asr.model is not None)
