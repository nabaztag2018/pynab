import sys, asyncio, json, datetime, sys
from nabcommon import nabservice
from mastodon import Mastodon, StreamListener, MastodonError

class NabMastodond(nabservice.NabService,asyncio.Protocol,StreamListener):
  RETRY_DELAY = 15 * 60 # Retry to reconnect every 15 minutes.

  def __init__(self):
    super().__init__()
    from . import models
    self.config = models.Config.load()
    self.mastodon_client = None
    self.mastodon_stream_handle = None
    self.current_access_token = None
    self.setup_streaming()

  async def reload_config(self):
    from django.core.cache import cache
    cache.clear()
    from . import models
    self.config = models.Config.load()
    self.setup_streaming()

  def close_streaming(self):
    if self.mastodon_stream_handle:
      self.mastodon_stream_handle.close()
    self.current_access_token = None
    self.mastodon_stream_handle = None
    self.mastodon_client = None

  def on_update(self, status):
    self.loop.call_soon_thread_safe(lambda : self.do_update(status))

  def do_update(self, status):
    (status_id, status_date) = self.process_status(status)
    if status_id != None and (self.config.last_processed_status_id == None or status_id > self.config.last_processed_status_id):
      self.config.last_processed_status_id = status_id
    if status_date != None and status_date > self.config.last_processed_status_date:
      self.config.last_processed_status_date = status_date
    self.config.save()

  def process_timeline(self, timeline):
    max_date = self.config.last_processed_status_date
    max_id = self.config.last_processed_status_id
    for status in timeline:
      (status_id, status_date) = self.process_status(status)
      if status_id != None and (max_id == None or status_id > max_id):
        max_id = status_id
      if status_date != None and max_date > status_date:
        max_date = status_date
    self.config.last_processed_status_date = max_date
    self.config.last_processed_status_id = max_id
    self.config.save()

  def process_status(self, status):
    try:
      status_id = status['id']
      status_date = status['created_at']
      skip = False
      if self.config.last_processed_status_id != None:
        skip = status_id <= self.config.last_processed_status_id
      skip = skip or self.config.last_processed_status_date > status_date
      if not skip:
        self.do_process_status(status)
      return (status_id, status_date)
    except KeyError as e:
      print(f'Unexpected status from mastodon, missing slot {e}\n{status}')
      return (None, None)

  def do_process_status(self, status):
    pass

  def setup_streaming(self):
    if self.config.access_token == None:
      self.close_streaming()
    else:
      if self.config.access_token != self.current_access_token:
        self.close_streaming()
      if self.mastodon_client == None:
        try:
          self.mastodon_client = Mastodon(client_id = self.config.client_id, \
            client_secret = self.config.client_secret, \
            access_token = self.config.access_token,
            api_base_url = 'https://' + self.config.instance)
          self.current_access_token = self.config.access_token
        except MastodonUnauthorizedError:
          self.current_access_token = None
          self.config.access_token = None
          self.config.save()
        except MastodonError as e:
          print(f'Unexpected mastodon error: {e}')
          self.loop.call_later(NabMastodond.RETRY_DELAY, self.setup_streaming)
      if self.mastodon_client != None and self.mastodon_stream_handle == None:
        self.mastodon_stream_handle = self.mastodon_client.stream_user(self, run_async=True, reconnect_async=True)
      timeline = self.mastodon_client.timeline(timeline="direct", since_id=self.config.last_processed_status_id)
      self.process_timeline(timeline)

  async def process_nabd_packet(self, packet):
    pass

  def run(self):
    super().connect()
    self.loop = asyncio.get_event_loop()
    if self.config.spouse_left_ear_position != None:
      packet = f'{{"type":"ears","left":{self.config.spouse_left_ear_position},"right":{self.config.spouse_right_ear_position}}}'
      self.writer.write(packet.encode('utf8'))
    try:
      self.loop.run_forever()
    except KeyboardInterrupt:
      pass
    finally:
      self.running = False  # signal to exit
      self.writer.close()
      self.close_streaming()
      tasks = asyncio.all_tasks(self.loop)
      for t in [t for t in tasks if not (t.done() or t.cancelled())]:
        self.loop.run_until_complete(t)    # give canceled tasks the last chance to run
      self.loop.close()

if __name__ == '__main__':
  NabMastodond.main(sys.argv[1:])
