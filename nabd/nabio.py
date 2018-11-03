import abc

class NabIO(object, metaclass=abc.ABCMeta):
  """ Interface for I/O interactions with a nabaztag """

  def set_ears(self, left_ear, right_ear):
    """ Set the position of ears (left & right) """
    raise NotImplementedError( 'Should have implemented' )

  def set_leds(self, left, center, right, nose, bottom):
    """ Set the leds. None means to turn them off. """
    raise NotImplementedError( 'Should have implemented' )

  def bind_button_event(self, loop, callback):
    """
    Define the callback for button events.
    callback is cb(event_type) with event_type being:
    - 'down'
    - 'up'
    - 'click'
    - 'doubleclick'

    Make sure the callback is called on the provided event loop, with loop.call_soon_threadsafe
    """
    raise NotImplementedError( 'Should have implemented' )

  def bind_ears_event(self, loop, callback):
    """
    Define the callback for ears events.
    callback is cb(left_ear, right_ear) with left_ear and right_ear being the positions.

    Make sure the callback is called on the provided event loop, with loop.call_soon_threadsafe
    """
    raise NotImplementedError( 'Should have implemented' )

  async def play_info(self, tempo, colors):
    """
    Play an info animation.
    tempo & colors are as described in the nabd protocol.
    Run the animation once and returns.

    If 'left'/'center'/'right'/'bottom'/'nose' slots are absent, the light is off.
    """
    raise NotImplementedError( 'Should have implemented' )

  async def play_sequence(self, sequence):
    """
    Play a sequence (sounds & choregraphy)
    sequence is as described in nabd protocol.
    """
    raise NotImplementedError( 'Should have implemented' )

  def cancel(self):
    """
    Cancel currently running sequence or info animation.
    """
    raise NotImplementedError( 'Should have implemented' )
