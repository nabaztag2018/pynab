import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class StartStopCommand(BaseCommand):
    def __process_one(self, app, command):
        service_file = os.path.join(settings.BASE_DIR, app, app + ".service")
        if os.path.exists(service_file):
            self.stdout.write(f"{app}", ending="")
            r = os.system(f"service {app} {command}")
            if r != 0:
                self.stdout.write(self.style.ERROR(" FAILED"))
                return 1
            else:
                self.stdout.write(self.style.SUCCESS(" OK"))
        return 0

    def do_handle(self, command):
        failed_count = 0
        if command == "start":
            failed_count += self.__process_one("nabd", command)
        for app in settings.INSTALLED_APPS:
            if app != "nabd":
                failed_count += self.__process_one(app, command)
        if command != "start":
            failed_count += self.__process_one("nabd", command)
        if failed_count > 0:
            raise CommandError(f"Failed to {command} one or more services")
