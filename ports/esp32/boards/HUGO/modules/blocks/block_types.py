class BlockType:
  def __init__(self, type: int, name: str):
    self.id:int = type
    self.name:bytes = name.encode("ascii")

class BlockTypes:
  power = BlockType(0x08, "power_block")
  rgb = BlockType(0x09, "rgb_block")
  motor_driver = BlockType(0x0a, "motor_block")
  display = BlockType(0x0b, "disp_block")
  sound = BlockType(0x0c, "sound_block")
  button = BlockType(0x0d, "button_block")
  distance = BlockType(0x0e, "distance_block")
  motion_tracking = BlockType(0x0f, "motion_tracking")
  ir = BlockType(0x10, "ir_block")
  ambient = BlockType(0x11, "ambient_block")
  ble = BlockType(0x12, "ble_block")
  rj12 = BlockType(0x13, "rj12_block")
  servo = BlockType(0x14, "servo_block")
  step_motor = BlockType(0x15, "step_motor_block")
