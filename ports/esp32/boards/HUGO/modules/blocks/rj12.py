#  Copyright (c) 2023 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

# pylint: disable=no-name-in-module
from blocks.block_types import BlockTypes
from blocks.block_base import BlockBase

class Rj12Block(BlockBase):
  def __init__(self, address=None, measurement_period: float=0.1):
    BlockBase.__init__(self, BlockTypes.rj12, address)
