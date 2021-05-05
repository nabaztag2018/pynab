import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class StartStopCommand(BaseCommand):
    def do_handle(self, command):
        failed_count = 0
        for app in settings.INSTALLED_APPS:
            if app != "nabd":
                service_file = os.path.join(
                    settings.BASE_DIR, app, app + ".service"
                )
                if os.path.exists(service_file):
                    self.stdout.write(f"{app}", ending="")
                    r = os.system(f"service {app} {command}")
                    if r != 0:
                        self.stdout.write(self.style.ERROR(" FAILED"))
                        failed_count += 1
                    else:
                        self.stdout.write(self.style.SUCCESS(" OK"))
        self.stdout.write("nabd", ending="")
        r = os.system(f"service nabd {command}")
        if r != 0:
            self.stdout.write(self.style.ERROR(" FAILED"))
            failed_count += 1
        else:
            self.stdout.write(self.style.SUCCESS(" OK"))
        if failed_count > 0:
            raise CommandError(f"Failed to {command} one or more services")
