add_library(usermod_zigbee INTERFACE)

target_sources(usermod_zigbee INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/modzigbee.c
)

target_link_libraries(usermod INTERFACE usermod_zigbee)
