#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

from micropython import const

cmd_common_version            = const(0x60)
cmd_common_last               = const(0x6f)

cmd_shell_program_started     = const(0x80)
cmd_shell_stop_program        = const(0x81)
cmd_shell_start_program       = const(0x82)
cmd_shell_get_next_file_info  = const(0x83)
cmd_shell_remove_file         = const(0x84)
cmd_shell_handle_file         = const(0x85)
cmd_shell_get_file_checksum   = const(0x86)
cmd_shell_append              = const(0x87)
cmd_shell_mk_dir              = const(0x88)
cmd_shell_last                = const(0x8f)

cmd_remote_val_get_all        = const(0xa0)

b_true = b"\1"
b_false = b"\0"
