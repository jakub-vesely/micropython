from main_block import MainBlock
main = MainBlock()

#from rgb_block import RgbBlock
#rgb = RgbBlock(0x10)

# def toggle_led():
#   rgb.toggle()
#   planner.postpone(1, toggle_led)

# def change_color(color):
#   rgb.set_color(color)
#   color = color + 1
#   if color < 15:
#     planner.postpone(0.5, change_color, color)
#   else:
#     planner.repeat(2, rgb.toggle)
#   #color = color + 1 if color < 14 else 1
#   #planner.postpone(0.5, change_color, color)

# def set_rgb_on():
#   rgb.set_on()
#   planner.postpone(0.5, set_rgb_off)

# def set_rgb_off():
#   rgb.set_off()
#   planner.postpone(0.5, set_rgb_on)

# def print_on(par1, par2):
#   print("RGB is ON " + par1 + par2)

#rgb.change_block_address(0x10)
#change_color(1)
#planner.postpone(0.5, change_color, 1)
#planner.repeat(0.5, rgb.toggle)

# def command_callback1(command):
#   print({"command": command})

# def command_callback(command, data):
#   print({"command": command, "data": data})

#import hugo_ble
#print(hugo_ble.initialize("HuGo", command_callback))

#rgb.state.equal_to_trigger(True, print_on, "hallo", par2=" world")
#rgb.state.equal_to_repeat_trigger(True, print_on, "BLA", par2=" bla")
#set_rgb_on()

main.run()

