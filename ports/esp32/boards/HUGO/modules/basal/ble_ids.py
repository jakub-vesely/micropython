#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

from micropython import const

class  RemoteValueId:
    added    = const(0x01)
    removed  = const(0x02)
    info     = const(0x03)

class CommandId:
    common_version            = const(0x60)
    common_last               = const(0x6f)

    shell_stop_program        = const(0x81)
    shell_start_program       = const(0x82)
    shell_get_next_file_info  = const(0x83)
    shell_remove_file         = const(0x84)
    shell_handle_file         = const(0x85)
    shell_get_file_checksum   = const(0x86)
    shell_append              = const(0x87)
    shell_mk_dir              = const(0x88)
    shell_last                = const(0x8f)
