from snips_nlu import SnipsNLUEngine
from pathlib import Path
from nabweb import settings
from concurrent.futures import ThreadPoolExecutor
import traceback


class NLU:
    """
    Class handling natural language understanding.
    """

    ENGINES = {
        "en_US": "nlu/engine_en/",
        "en_GB": "nlu/engine_en/",
        "fr_FR": "nlu/engine_fr/",
    }
    DEFAULT_LOCALE = "fr_FR"

    @staticmethod
    def get_locale(locale):
        if locale in NLU.ENGINES:
            return locale
        else:
            return NLU.DEFAULT_LOCALE

    def __init__(self, locale):
        self.executor = ThreadPoolExecutor(max_workers=1)
        self._load_model(locale)

    def _load_model(self, locale):
        try:
            locale = NLU.get_locale(locale)
            path = NLU.ENGINES[locale]
            basepath = Path(settings.BASE_DIR)
            fullpath = basepath.joinpath("nabd", path).as_posix()
            self.nlu_engine = SnipsNLUEngine.from_path(fullpath)
        except Exception:
            print(traceback.format_exc())

    async def interpret(self, string):
        """
        Interpret string from asr.
        Return None if interpretation failed.
        """
        future = self.executor.submit(lambda s=string: self._interpret(s))
        return future.result()

    def _interpret(self, string):
        try:
            if string == "":
                return None
            # TODO : hardcode magic 8 ball ?
            parsed = self.nlu_engine.parse(string)
            if parsed["intent"]["intentName"] is None:
                return None
            result = {"intent": parsed["intent"]["intentName"]}
            for slot in parsed["slots"]:
                result[slot["slotName"]] = slot["value"]["value"]
            return result
        except Exception:
            print(traceback.format_exc())
            return None
