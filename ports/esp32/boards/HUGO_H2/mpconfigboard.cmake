include(boards/mpconfigboard_esp32h2_common.cmake)

set(SDKCONFIG_DEFAULTS
    boards/sdkconfig.base
    boards/sdkconfig.riscv
    boards/sdkconfig.ble
    ${MICROPY_BOARD_DIR}/sdkconfig.zigbee
)

if(NOT MICROPY_FROZEN_MANIFEST)
    set(MICROPY_FROZEN_MANIFEST ${MICROPY_BOARD_DIR}/manifest.py)
endif()