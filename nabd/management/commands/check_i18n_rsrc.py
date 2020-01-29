import os
import re

from django.core.management.base import BaseCommand
from django.conf import settings

LANGUAGES = [
    "de_DE",
    "en_GB",
    "en_US",
    "es_ES",
    "fr_FR",
    "it_IT",
    "ja_JP",
    "pt_BR",
]


class Command(BaseCommand):
    help = "Check for missing international resources (sounds)"

    def add_arguments(self, parser):
        parser.add_argument("app", nargs="*", type=str)

    def handle(self, *args, **options):
        if options["app"] == []:
            apps = []
            for app in settings.INSTALLED_APPS:
                app_dir = os.path.join(settings.BASE_DIR, app)
                if os.path.exists(app_dir):
                    apps.append(app)
        else:
            apps = options["app"]
        for app in apps:
            for rsrc in ["sounds", "choreographies"]:
                resources = {}
                for lang in LANGUAGES:
                    lang_dir = os.path.join(settings.BASE_DIR, app, rsrc, lang)
                    if os.path.exists(lang_dir):
                        for root, dirs, files in os.walk(lang_dir):
                            relroot = root[len(lang_dir) + 1 :]
                            # Determine if it's a random list of files
                            rand_pattern = self.random_list_pattern(files)
                            if rand_pattern:
                                relpath = os.path.join(relroot, rand_pattern)
                                if relpath in resources:
                                    langlist = resources[relpath]
                                else:
                                    langlist = []
                                langlist.append(lang)
                                resources[relpath] = langlist                                
                            else:
                                for file in files:
                                    if file.startswith("."):
                                        continue
                                    relpath = os.path.join(relroot, file)
                                    if relpath in resources:
                                        langlist = resources[relpath]
                                    else:
                                        langlist = []
                                    langlist.append(lang)
                                    resources[relpath] = langlist
                for resource, langs in dict.items(resources):
                    if len(langs) < len(LANGUAGES):
                        missing_langs = set(LANGUAGES) - set(langs)
                        self.stdout.write(
                            self.style.ERROR(
                                f"Missing {resource} for {missing_langs}"
                            )
                        )

    def random_list_pattern(self, files):
        filtered_files = [file for file in files if not file.startswith(".")]
        if filtered_files == []:
            return None
        first_file = filtered_files[0]
        m = re.search("^([^0-9]*)(?:[0-9]+B?)\\.([^\\.]+)$", first_file)
        if m:
            prefix = m.group(1)
            suffix = m.group(2)
            for file in filtered_files:
                m = re.search("^([^0-9]*)(?:[0-9]+B?)\\.([^.]+)$", file)
                if not m:
                    return None
                if prefix != m.group(1) or suffix != m.group(2):
                    return None
            return "*." + suffix
