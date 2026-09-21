// Zigbee temperature sensor binding for the HuGo ESP32-H2 board.
// The Zigbee task never calls into the MicroPython VM.

#include <stdint.h>

#include "esp_err.h"
#define LOG_LOCAL_LEVEL ESP_LOG_INFO
#include "esp_log.h"
#include "esp_timer.h"
#include "esp_zigbee.h"
#include "ezbee/zha.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "py/mperrno.h"
#include "py/runtime.h"

#define HUGO_ZIGBEE_ENDPOINT 10
#define HUGO_ZIGBEE_PRIMARY_CHANNEL (1U << 13)
#define HUGO_ZIGBEE_SECONDARY_CHANNELS 0x07fff800U

static const char *TAG = "hugo_zigbee";
// Keep the identity of the Espressif example for the initial ZHA test.
static const char manufacturer_name[] = "\x09" "ESPRESSIF";
static const char model_identifier[] = "\x07" CONFIG_IDF_TARGET;

static volatile bool zigbee_started;
static volatile bool zigbee_ready;
static volatile bool zigbee_joined;
static volatile bool zigbee_startup_signal_seen;
static volatile int zigbee_initialization_status = -1;
static volatile int zigbee_factory_new = -1;
static volatile int zigbee_last_steering_status = -1;
static volatile ezb_err_t zigbee_last_error = EZB_ERR_NONE;
static esp_timer_handle_t zigbee_init_retry_timer;

static void zigbee_schedule_initialization_retry(void) {
    if (zigbee_init_retry_timer != NULL) {
        esp_err_t result = esp_timer_start_once(zigbee_init_retry_timer, 1000000);
        if (result != ESP_OK) {
            ESP_LOGE(TAG, "Unable to schedule Zigbee initialization retry: 0x%x", result);
        }
    }
}

static void zigbee_retry_initialization(void *arg) {
    (void)arg;
    if (!zigbee_ready || zigbee_factory_new != -1) {
        return;
    }
    if (!esp_zigbee_lock_acquire(pdMS_TO_TICKS(1000))) {
        zigbee_schedule_initialization_retry();
        return;
    }
    zigbee_last_error = ezb_bdb_start_top_level_commissioning(EZB_BDB_MODE_INITIALIZATION);
    esp_zigbee_lock_release();
    if (zigbee_last_error != EZB_ERR_NONE) {
        ESP_LOGE(TAG, "Zigbee initialization retry rejected: 0x%x", zigbee_last_error);
        zigbee_schedule_initialization_retry();
    }
}

static bool zigbee_signal_handler(const ezb_app_signal_t *signal) {
    ezb_app_signal_type_t type = ezb_app_signal_get_type(signal);
    switch (type) {
        case EZB_ZDO_SIGNAL_SKIP_STARTUP:
            zigbee_startup_signal_seen = true;
            zigbee_last_error = ezb_bdb_start_top_level_commissioning(EZB_BDB_MODE_INITIALIZATION);
            if (zigbee_last_error != EZB_ERR_NONE) {
                ESP_LOGE(TAG, "Zigbee initialization request rejected: 0x%x", zigbee_last_error);
                zigbee_schedule_initialization_retry();
            }
            break;

        case EZB_BDB_SIGNAL_DEVICE_FIRST_START:
        case EZB_BDB_SIGNAL_DEVICE_REBOOT: {
            ezb_bdb_comm_status_t status = *(ezb_bdb_comm_status_t *)ezb_app_signal_get_params(signal);
            zigbee_initialization_status = status;
            if (status == EZB_BDB_STATUS_SUCCESS) {
                zigbee_factory_new = ezb_bdb_is_factory_new();
                zigbee_joined = ezb_bdb_dev_joined();
                if (zigbee_factory_new) {
                    zigbee_last_error = ezb_bdb_start_top_level_commissioning(EZB_BDB_MODE_NETWORK_STEERING);
                } else {
                    ESP_LOGI(TAG, "Restoring saved Zigbee network; joined=%d", zigbee_joined);
                }
            } else {
                ESP_LOGE(TAG, "Zigbee initialization failed: 0x%x", status);
                zigbee_schedule_initialization_retry();
            }
            break;
        }

        case EZB_BDB_SIGNAL_STEERING: {
            ezb_bdb_comm_status_t status = *(ezb_bdb_comm_status_t *)ezb_app_signal_get_params(signal);
            zigbee_last_steering_status = status;
            zigbee_joined = (status == EZB_BDB_STATUS_SUCCESS);
            if (zigbee_joined) {
                ESP_LOGI(TAG, "Joined Zigbee network");
            } else {
                ESP_LOGW(TAG, "Zigbee join failed: 0x%x; reopen pairing and call zigbee.join()", status);
            }
            break;
        }

        case EZB_ZDO_SIGNAL_LEAVE:
            zigbee_joined = false;
            ESP_LOGI(TAG, "Left Zigbee network");
            break;

        default:
            break;
    }
    return true;
}

static esp_err_t zigbee_register_sensor(void) {
    ezb_af_device_desc_t device = ezb_af_create_device_desc();
    ezb_zha_temperature_sensor_config_t config = EZB_ZHA_TEMPERATURE_SENSOR_CONFIG();
    config.temp_meas_cfg.min_measured_value = -1000;
    config.temp_meas_cfg.max_measured_value = 8000;

    ezb_af_ep_desc_t endpoint = ezb_zha_create_temperature_sensor(HUGO_ZIGBEE_ENDPOINT, &config);
    ezb_zcl_cluster_desc_t basic = ezb_af_endpoint_get_cluster_desc(
        endpoint, EZB_ZCL_CLUSTER_ID_BASIC, EZB_ZCL_CLUSTER_SERVER);
    ezb_zcl_basic_cluster_desc_add_attr(
        basic, EZB_ZCL_ATTR_BASIC_MANUFACTURER_NAME_ID, (void *)manufacturer_name);
    ezb_zcl_basic_cluster_desc_add_attr(
        basic, EZB_ZCL_ATTR_BASIC_MODEL_IDENTIFIER_ID, (void *)model_identifier);

    if (ezb_af_device_add_endpoint_desc(device, endpoint) != EZB_ERR_NONE ||
        ezb_af_device_desc_register(device) != EZB_ERR_NONE) {
        return ESP_FAIL;
    }
    return ESP_OK;
}

static void zigbee_task(void *arg) {
    esp_log_level_set(TAG, ESP_LOG_INFO);
    esp_zigbee_config_t config = {
        .device_config = {
            .device_type = EZB_NWK_DEVICE_TYPE_END_DEVICE,
            .install_code_policy = false,
            .zed_config = {
                .ed_timeout = EZB_NWK_ED_TIMEOUT_64MIN,
                .keep_alive = 4000,
            },
        },
        .platform_config = {
            .storage_partition_name = "nvs",
            .radio_config = {
                .radio_mode = ESP_ZIGBEE_RADIO_MODE_NATIVE,
            },
        },
    };

    if (esp_zigbee_init(&config) != ESP_OK) {
        ESP_LOGE(TAG, "esp_zigbee_init failed");
        goto done;
    }
    esp_timer_create_args_t retry_timer_args = {
        .callback = zigbee_retry_initialization,
        .name = "zigbee_init_retry",
    };
    if (esp_timer_create(&retry_timer_args, &zigbee_init_retry_timer) != ESP_OK) {
        ESP_LOGE(TAG, "Unable to create Zigbee initialization retry timer");
        goto done;
    }
    ezb_aps_secur_enable_distributed_security(false);
    if (ezb_bdb_set_primary_channel_set(HUGO_ZIGBEE_PRIMARY_CHANNEL) != EZB_ERR_NONE ||
        ezb_bdb_set_secondary_channel_set(HUGO_ZIGBEE_SECONDARY_CHANNELS) != EZB_ERR_NONE ||
        ezb_app_signal_add_handler(zigbee_signal_handler) != EZB_ERR_NONE ||
        zigbee_register_sensor() != ESP_OK ||
        esp_zigbee_start(false) != ESP_OK) {
        ESP_LOGE(TAG, "Zigbee setup failed");
        goto done;
    }

    zigbee_ready = true;
    ESP_LOGI(TAG, "Zigbee temperature sensor started");
    esp_zigbee_launch_mainloop();
    zigbee_ready = false;
    zigbee_joined = false;
    esp_zigbee_deinit();

done:
    if (zigbee_init_retry_timer != NULL) {
        esp_timer_stop(zigbee_init_retry_timer);
        esp_timer_delete(zigbee_init_retry_timer);
        zigbee_init_retry_timer = NULL;
    }
    zigbee_started = false;
    vTaskDelete(NULL);
}

static mp_obj_t zigbee_start(void) {
    if (!zigbee_started) {
        zigbee_startup_signal_seen = false;
        zigbee_initialization_status = -1;
        zigbee_factory_new = -1;
        zigbee_last_steering_status = -1;
        zigbee_last_error = EZB_ERR_NONE;
        zigbee_started = true;
        if (xTaskCreate(zigbee_task, "hugo_zigbee", 4096, NULL, 5, NULL) != pdPASS) {
            zigbee_started = false;
            mp_raise_OSError(MP_ENOMEM);
        }
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(zigbee_start_obj, zigbee_start);

static mp_obj_t zigbee_is_joined(void) {
    return mp_obj_new_bool(zigbee_joined);
}
static MP_DEFINE_CONST_FUN_OBJ_0(zigbee_is_joined_obj, zigbee_is_joined);

static mp_obj_t zigbee_status(void) {
    mp_obj_t status = mp_obj_new_dict(0);
    mp_obj_dict_store(status, MP_OBJ_NEW_QSTR(MP_QSTR_started), mp_obj_new_bool(zigbee_started));
    mp_obj_dict_store(status, MP_OBJ_NEW_QSTR(MP_QSTR_ready), mp_obj_new_bool(zigbee_ready));
    mp_obj_dict_store(status, MP_OBJ_NEW_QSTR(MP_QSTR_joined), mp_obj_new_bool(zigbee_joined));
    mp_obj_dict_store(status, MP_OBJ_NEW_QSTR(MP_QSTR_startup_seen), mp_obj_new_bool(zigbee_startup_signal_seen));
    mp_obj_dict_store(status, MP_OBJ_NEW_QSTR(MP_QSTR_initialization_status), mp_obj_new_int(zigbee_initialization_status));
    mp_obj_dict_store(status, MP_OBJ_NEW_QSTR(MP_QSTR_factory_new), mp_obj_new_int(zigbee_factory_new));
    mp_obj_dict_store(status, MP_OBJ_NEW_QSTR(MP_QSTR_steering_status), mp_obj_new_int(zigbee_last_steering_status));
    mp_obj_dict_store(status, MP_OBJ_NEW_QSTR(MP_QSTR_last_error), mp_obj_new_int(zigbee_last_error));
    return status;
}
static MP_DEFINE_CONST_FUN_OBJ_0(zigbee_status_obj, zigbee_status);

static mp_obj_t zigbee_join(void) {
    if (!zigbee_ready || zigbee_initialization_status != EZB_BDB_STATUS_SUCCESS) {
        mp_raise_OSError(MP_ENODEV);
    }
    if (!zigbee_joined) {
        if (!esp_zigbee_lock_acquire(pdMS_TO_TICKS(1000))) {
            mp_raise_OSError(MP_ETIMEDOUT);
        }
        ezb_err_t result = ezb_bdb_start_top_level_commissioning(EZB_BDB_MODE_NETWORK_STEERING);
        zigbee_last_error = result;
        esp_zigbee_lock_release();
        if (result != EZB_ERR_NONE) {
            mp_raise_OSError(MP_EIO);
        }
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(zigbee_join_obj, zigbee_join);

static mp_obj_t zigbee_set_temperature(mp_obj_t temperature_obj) {
    mp_float_t temperature = mp_obj_get_float(temperature_obj);
    if (!(temperature >= -10.0 && temperature <= 80.0)) {
        mp_raise_ValueError(MP_ERROR_TEXT("temperature outside -10..80 C"));
    }
    if (!zigbee_ready || !zigbee_joined) {
        mp_raise_OSError(MP_ENOTCONN);
    }

    int16_t measured_value = (int16_t)(temperature * 100);
    ezb_zcl_report_attr_cmd_t report = {
        .cmd_ctrl = {
            .fc.direction = EZB_ZCL_CMD_DIRECTION_TO_CLI,
            .dst_addr.addr_mode = EZB_ADDR_MODE_NONE,
            .src_ep = HUGO_ZIGBEE_ENDPOINT,
            .cluster_id = EZB_ZCL_CLUSTER_ID_TEMPERATURE_MEASUREMENT,
        },
        .payload = {
            .attr_id = EZB_ZCL_ATTR_TEMPERATURE_MEASUREMENT_MEASURED_VALUE_ID,
        },
    };

    if (!esp_zigbee_lock_acquire(pdMS_TO_TICKS(1000))) {
        mp_raise_OSError(MP_ETIMEDOUT);
    }
    ezb_zcl_status_t update = ezb_zcl_set_attr_value(
        HUGO_ZIGBEE_ENDPOINT, EZB_ZCL_CLUSTER_ID_TEMPERATURE_MEASUREMENT,
        EZB_ZCL_CLUSTER_SERVER, EZB_ZCL_ATTR_TEMPERATURE_MEASUREMENT_MEASURED_VALUE_ID,
        EZB_ZCL_STD_MANUF_CODE, &measured_value, false);
    ezb_err_t send = EZB_ERR_NONE;
    if (update == EZB_ZCL_STATUS_SUCCESS) {
        send = ezb_zcl_report_attr_cmd_req(&report);
    }
    esp_zigbee_lock_release();
    if (update != EZB_ZCL_STATUS_SUCCESS || send != EZB_ERR_NONE) {
        mp_raise_OSError(MP_EIO);
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(zigbee_set_temperature_obj, zigbee_set_temperature);

static const mp_rom_map_elem_t zigbee_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_zigbee) },
    { MP_ROM_QSTR(MP_QSTR_start), MP_ROM_PTR(&zigbee_start_obj) },
    { MP_ROM_QSTR(MP_QSTR_joined), MP_ROM_PTR(&zigbee_is_joined_obj) },
    { MP_ROM_QSTR(MP_QSTR_status), MP_ROM_PTR(&zigbee_status_obj) },
    { MP_ROM_QSTR(MP_QSTR_join), MP_ROM_PTR(&zigbee_join_obj) },
    { MP_ROM_QSTR(MP_QSTR_set_temperature), MP_ROM_PTR(&zigbee_set_temperature_obj) },
};
static MP_DEFINE_CONST_DICT(zigbee_globals, zigbee_globals_table);

const mp_obj_module_t zigbee_module = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&zigbee_globals,
};
MP_REGISTER_MODULE(MP_QSTR_zigbee, zigbee_module);
