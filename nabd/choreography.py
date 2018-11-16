import random, time, asyncio
from .resources import Resources

class ChoreographyInterpreter:
  def __init__(self, leds, ears, sound):
    self.timescale = 0
    self.leds = leds
    self.ears = ears
    self.sound = sound

  # from nominal.010120_as3.mtl
  MTL_OPCODE_HANDLDERS = [
    'nop',
    'frame_duration',
    'undefined',
    'undefined',
    'undefined',
    'undefined',
    'undefined',        # 'set_color', but commented
    'set_led_color',
    'set_motor',
    'set_leds_color',   # v16
    'set_led_off',      # v17
    'undefined',
    'undefined',
    'undefined',
    'set_led_palette',
    'undefined',        # 'set_palette', but commented
    'randmidi',
    'avance',
    'ifne',             # only used for taichi
    'attend',
    'setmotordir',      # v16
  ]

  # from Nabaztag_wait.vasm
  VASM_OPCODE_HANDLERS = [
    'nop',
    'frame_duration',
    'play_midi',
    'stop_midi',
    'play_sound',
    'stop_sound',
    'echo',
    'set_led_color',
    'set_motor',
    'avance',
    'attend',
    'end',
    'wait_music',
    'set',
    'ifne',
    'rand',
  ]

  MIDI_LIST = [
	  'choreographies/1noteA4.mp3',
	  'choreographies/1noteB5.mp3',
	  'choreographies/1noteBb4.mp3',
	  'choreographies/1noteC5.mp3',
	  'choreographies/1noteE4.mp3',
	  'choreographies/1noteF4.mp3',
	  'choreographies/1noteF5.mp3',
	  'choreographies/1noteG5.mp3',
	  'choreographies/2notesC6C4.mp3',
	  'choreographies/2notesC6F5.mp3',
	  'choreographies/2notesD4A5.mp3',
	  'choreographies/2notesD4G4.mp3',
	  'choreographies/2notesD5G4.mp3',
	  'choreographies/2notesE5A5.mp3',
	  'choreographies/2notesE5C6.mp3',
	  'choreographies/2notesE5E4.mp3',
	  'choreographies/3notesA4G5G5.mp3',
	  'choreographies/3notesB5A5F5.mp3',
	  'choreographies/3notesB5D5C6.mp3',
	  'choreographies/3notesD4E4G4.mp3',
	  'choreographies/3notesE5A5C6.mp3',
	  'choreographies/3notesE5C6D5.mp3',
	  'choreographies/3notesE5D5A5.mp3',
	  'choreographies/3notesF5C6G5.mp3'
  ]

  OPCODE_HANDLERS = {'mtl': MTL_OPCODE_HANDLDERS, 'vasm': VASM_OPCODE_HANDLERS}

  async def nop(self, index, chor):
    return index

  async def frame_duration(self, index, chor):
    self.timescale = chor[index]
    return index + 1

  async def set_led_color(self, index, chor):
    led = chor[index]
    r = chor[index + 1]
    g = chor[index + 2]
    b = chor[index + 3]
    self.leds.set1(led, r, g, b)
    return index + 6

  async def set_motor(self, index, chor):
    motor = chor[index]
    position = chor[index + 1]
    direction = chor[index + 2]
    await self.ears.go(motor, position, direction)
    return index + 3

  async def set_leds_color(self, index, chor):
    r = chor[index]
    g = chor[index + 1]
    b = chor[index + 2]
    self.leds.setall(r, g, b)
    return index + 3

  async def set_led_off(self, index, chor):
    led = chor[index]
    self.leds.set1(led, 0, 0, 0)
    return index + 1

  async def set_led_palette(self, index, chor):
    led = chor[index]
    palette_ix = chor[index + 1] & 7
    (r, g, b) = self.current_palette[palette_ix]
    self.leds.set1(led, r, g, b)
    return index + 2

  async def randmidi(self, index, chor):
    await self.sound.start(random.choice(ChoreographyInterpreter.MIDI_LIST))
    return index

  async def avance(self, index, chor):
    motor = chor[index]
    delta = chor[index + 1]
    direction = self.taichi_directions[motor]
    if direction:
      delta = -delta
    await self.ears.move(motor, delta, direction)
    return index + 2

  async def ifne(self, index, chor):
    if self.taichi_random == chor[index]:
      return index + 3
    rel = (chor[index + 1] << 8) + chor[index + 2]
    if rel >= 32768:    # assumed signed (?)
      rel = rel - 65536
    return index + rel + 3

  async def attend(self, index, chor):
    await self.ears.wait_while_running()
    await self.sound.wait_until_done()
    return index

  async def setmotordir(self, index, chor):
    motor = chor[index]
    dir = chor[index + 1]
    self.taichi_directions[motor] = dir
    return index + 2

  async def play_binary(self, chor, opcodes='mtl'):
    if chor[0] == 1 and chor[1] == 1 and chor[2] == 1 and chor[3] == 1:
      # Consider this is the header
      await self.do_play_binary(4, chor, opcodes)
    else:
      await self.do_play_binary(0, chor, opcodes)

  async def do_play_binary(self, start_index, chor, opcodes):
    index = start_index
    self.timescale = 0
    # These are apparently for taichi (only ?)
    self.taichi_random = int(random.randint(0, 255) * 30 >> 8)
    self.taichi_directions = [0, 0]
    self.current_palette = [(0, 0, 0) for x in range(8)]

    next_time = time.time()
    opcode_handlers = ChoreographyInterpreter.OPCODE_HANDLERS[opcodes]
    while index < len(chor):
      wait = chor[index]
      # do some wait now
      next_time = next_time + (wait * self.timescale / 1000.0)
      sleep_delta = next_time - time.time()
      if sleep_delta > 0:
        await asyncio.sleep(sleep_delta)
      index = index + 2
      if index >= len(chor):
        # taichi.chor ends with a wait
        break
      opcode = chor[index - 1]
      try:
        opcode_handler = opcode_handlers[opcode]
        handler = getattr(self, opcode_handler)
      except IndexError as err:
        # 255 apparently used for end.
        if opcode != 255:
          print('Unknown opcode {opcode}'.format(opcode=opcode))
        return
      except AttributeError as err:
        print('Unknown opcode {opcode} {err}'.format(opcode=opcode, err=err))
        return
      index = await handler(index, chor)

  async def play(self, ref):
    # Assume a resource for now.
    file = Resources.find('choreographies', ref)
    chor = file.read_bytes()
    await self.play_binary(chor)
