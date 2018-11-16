import abc

class Ears(object, metaclass=abc.ABCMeta):
  """ Interface for ears """
  LEFT_EAR = 0
  RIGHT_EAR = 1

  FORWARD_DIRECTION = 0
  BACKWARD_DIRECTION = 1

  STEPS = 17

  async def reset_ears(self):
    """ Reset the ears to a known position """
    raise NotImplementedError( 'Should have implemented' )

  async def move(self, ear, delta, direction):
    """ Move by an increment in a given direction """
    raise NotImplementedError( 'Should have implemented' )

  async def go(self, ear, position, direction):
    """
    Go to a specific position
    If position is not within 0-(STEPS-1), it represents additional turns.
    For example, STEPS means to position the ear at 0 after at least a complete turn.
    """
    raise NotImplementedError( 'Should have implemented' )

  async def wait_while_running(self):
    """ Wait until both motors have stopped as ears reached their target position """
    raise NotImplementedError( 'Should have implemented' )
