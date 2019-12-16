import os
import glob

from django.core.management.base import BaseCommand, CommandError
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
                            if self.is_random_list(files):
                                pass
                            else:
                                for file in files:
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

    def is_random_list(self, files):
        # every file has the same suffix
        # and of the form [prefix][0-9]+\.suffix
        return False
