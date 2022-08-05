#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

class BlockList():
    _blocks = list()

    @staticmethod
    def add_block(block:object):
        BlockList._blocks.append(block)

    @staticmethod
    def get_blocks():
        return BlockList._blocks
