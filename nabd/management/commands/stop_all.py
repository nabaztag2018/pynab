from ._start_stop_all import StartStopCommand

class Command(StartStopCommand):
    help = 'Stop all nab services'

    def handle(self, *args, **options):
        self.do_handle("stop")
