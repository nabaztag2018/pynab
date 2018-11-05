import asyncio, os, json
from django.conf import settings
from django.apps import apps
from nabd import nabd

class NabService:
  def __init__(self):
    if not settings.configured:
      conf = {
        'INSTALLED_APPS': [
          type(self).__name__
        ],
        'DATABASES': {
          'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'pynab',
            'USER': 'pynab',
            'PASSWORD': '',
            'HOST': '',
            'PORT': '',
          }
        }
      }
      settings.configure(**conf)
      apps.populate(settings.INSTALLED_APPS)
    self.reader = None
    self.writer = None
    self.loop = None
    self.running = True

  async def process_nabd_packet(self, packet):
    pass

  async def client_loop(self):
    try:
      while self.running:
        line = await self.reader.readline()
        if line != b'' and line != b'\r\n':
          try:
            packet = json.loads(line)
            await self.process_nabd_packet(packet)
          except json.decoder.JSONDecodeError as e:
            print(f'Invalid JSON packet from nabd: {line}\n{str(e)}')
    except KeyboardInterrupt:
      pass
    finally:
      if self.running:
        self.loop.stop()

  def connect(self):
    loop = asyncio.get_event_loop()
    connection = asyncio.open_connection(host="127.0.0.1", port=nabd.Nabd.PORT_NUMBER)
    try:
      (reader, writer) = loop.run_until_complete(connection)
    except ConnectionRefusedError:
      print('Could not connect to server. Is nabd running?')
      exit(1)
    self.reader = reader
    self.writer = writer
    loop.create_task(self.client_loop())
