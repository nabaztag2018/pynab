from ._start_stop_all import StartStopCommand

class Command(BaseCommand):
    help = 'Start all nab services'

    def handle(self, *args, **options):
        self.do_handle("stop")
