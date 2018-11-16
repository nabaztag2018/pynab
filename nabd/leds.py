import abc

class Leds(object, metaclass=abc.ABCMeta):
  """ Interface for leds """

  LED_NOSE = 0
  LED_LEFT = 1
  LED_CENTER = 2
  LED_RIGHT = 3
  LED_BOTTOM = 4

  def set1(self, led, red, green, blue):
    """
    Set the color of a given led.
    """
    raise NotImplementedError( 'Should have implemented' )

  def setall(self, led, red, green, blue):
    """
    Set the color of every led.
    """
    raise NotImplementedError( 'Should have implemented' )
