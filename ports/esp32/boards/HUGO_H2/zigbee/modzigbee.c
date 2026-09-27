// Configurable Zigbee sensor binding for the HuGo ESP32-H2 board.
// The Zigbee task never calls into the MicroPython VM.

#include <stdint.h>
#include <string.h>

#include "esp_err.h"
#define LOG_LOCAL_LEVEL ESP_LOG_INFO
#include "esp_log.h"
#include "esp_timer.h"
#include "esp_zigbee.h"
#include "ezbee/zha.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "py/mperrno.h"
#include "py/obj.h"
#include "py/runtime.h"

#define HUGO_ZIGBEE_ELECTRICAL_ENDPOINT 1
#define HUGO_ZIGBEE_WEATHER_ENDPOINT 2
#define HUGO_ZIGBEE_ENVIRONMENT_CLUSTER 0xfc00
#define HUGO_ZIGBEE_ATTR_WIND_DIRECTION 0x0000
#define HUGO_ZIGBEE_ATTR_RAIN_AMOUNT 0x0001
#define HUGO_ZIGBEE_MAX_SENSORS 16
#define HUGO_ZIGBEE_PRIMARY_CHANNEL (1U << 13)
#define HUGO_ZIGBEE_SECONDARY_CHANNELS 0x07fff800U
#define HUGO_ZIGBEE_MIN_JOIN_LQI 0

typedef enum {
    HUGO_SENSOR_DC_VOLTAGE,
    HUGO_SENSOR_DC_CURRENT,
    HUGO_SENSOR_TEMPERATURE,
    HUGO_SENSOR_HUMIDITY,
    HUGO_SENSOR_PRESSURE,
    HUGO_SENSOR_WIND_SPEED,
    HUGO_SENSOR_CO2,
    HUGO_SENSOR_WIND_DIRECTION,
    HUGO_SENSOR_RAIN_AMOUNT,
} hugo_sensor_kind_t;

typedef struct {
    uint8_t endpoint_id;
    uint16_t cluster_id;
    uint16_t attribute_id;
    hugo_sensor_kind_t kind;
} hugo_sensor_config_t;

typedef struct {
    mp_obj_base_t base;
    uint8_t sensor_index;
} hugo_sensor_obj_t;

static const char *TAG = "hugo_zigbee";
static const char manufacturer_name[] = "\x04" "HuGo";
static const char model_identifier[] = "\x07" CONFIG_IDF_TARGET;

static volatile bool zigbee_started;
static volatile bool zigbee_ready;
static volatile bool zigbee_joined;
static volatile bool zigbee_steering_in_progress;
static volatile bool zigbee_rejoining;
static volatile bool zigbee_startup_signal_seen;
static volatile int zigbee_initialization_status = -1;
static volatile int zigbee_factory_new = -1;
static volatile int zigbee_last_steering_status = -1;
static volatile ezb_err_t zigbee_last_error = EZB_ERR_NONE;
static esp_timer_handle_t zigbee_init_retry_timer;
static hugo_sensor_config_t zigbee_sensors[HUGO_ZIGBEE_MAX_SENSORS];
static size_t zigbee_sensor_count;

extern const mp_obj_type_t zigbee_sensor_type;

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
            zigbee_rejoining = type == EZB_BDB_SIGNAL_DEVICE_REBOOT && status != EZB_BDB_STATUS_SUCCESS;
            if (status == EZB_BDB_STATUS_SUCCESS) {
                zigbee_rejoining = false;
                zigbee_factory_new = ezb_bdb_is_factory_new();
                zigbee_joined = ezb_bdb_dev_joined();
                if (zigbee_factory_new) {
                    zigbee_last_error = ezb_bdb_start_top_level_commissioning(EZB_BDB_MODE_NETWORK_STEERING);
                    zigbee_steering_in_progress = zigbee_last_error == EZB_ERR_NONE;
                    if (zigbee_steering_in_progress) {
                        zigbee_last_steering_status = -1;
                    }
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
            zigbee_steering_in_progress = false;
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
            zigbee_steering_in_progress = false;
            zigbee_rejoining = false;
            ESP_LOGI(TAG, "Left Zigbee network");
            break;

        default:
            break;
    }
    return true;
}

static bool zigbee_endpoint_has_cluster(uint8_t endpoint_id, uint16_t cluster_id) {
    for (size_t i = 0; i < zigbee_sensor_count; ++i) {
        if (zigbee_sensors[i].endpoint_id == endpoint_id && zigbee_sensors[i].cluster_id == cluster_id) {
            return true;
        }
    }
    return false;
}

static bool zigbee_endpoint_has_sensor(uint8_t endpoint_id, hugo_sensor_kind_t kind) {
    for (size_t i = 0; i < zigbee_sensor_count; ++i) {
        if (zigbee_sensors[i].endpoint_id == endpoint_id && zigbee_sensors[i].kind == kind) {
            return true;
        }
    }
    return false;
}

static ezb_zcl_cluster_desc_t zigbee_create_electrical_cluster(uint8_t endpoint_id) {
    ezb_zcl_electrical_measurement_cluster_server_config_t config = {
        .measurement_type = EZB_ZCL_ELECTRICAL_MEASUREMENT_MEASUREMENT_TYPE_DC_MEASUREMENT,
    };
    ezb_zcl_cluster_desc_t cluster = ezb_zcl_electrical_measurement_create_cluster_desc(
        &config, EZB_ZCL_CLUSTER_SERVER);
    if (cluster == EZB_INVALID_ZCL_CLUSTER_DESC) {
        return cluster;
    }

    const uint16_t multiplier = 1;
    if (zigbee_endpoint_has_sensor(endpoint_id, HUGO_SENSOR_DC_VOLTAGE)) {
        const int16_t measured = (int16_t)0x8000;
        const uint16_t divisor = 100;
        if (ezb_zcl_electrical_measurement_cluster_desc_add_attr(
                cluster, EZB_ZCL_ATTR_ELECTRICAL_MEASUREMENT_DC_VOLTAGE_ID, &measured) != EZB_ERR_NONE ||
            ezb_zcl_electrical_measurement_cluster_desc_add_attr(
                cluster, EZB_ZCL_ATTR_ELECTRICAL_MEASUREMENT_DC_VOLTAGE_MULTIPLIER_ID, &multiplier) != EZB_ERR_NONE ||
            ezb_zcl_electrical_measurement_cluster_desc_add_attr(
                cluster, EZB_ZCL_ATTR_ELECTRICAL_MEASUREMENT_DC_VOLTAGE_DIVISOR_ID, &divisor) != EZB_ERR_NONE) {
            return EZB_INVALID_ZCL_CLUSTER_DESC;
        }
    }
    if (zigbee_endpoint_has_sensor(endpoint_id, HUGO_SENSOR_DC_CURRENT)) {
        const int16_t measured = (int16_t)0x8000;
        const uint16_t divisor = 10000;
        if (ezb_zcl_electrical_measurement_cluster_desc_add_attr(
                cluster, EZB_ZCL_ATTR_ELECTRICAL_MEASUREMENT_DC_CURRENT_ID, &measured) != EZB_ERR_NONE ||
            ezb_zcl_electrical_measurement_cluster_desc_add_attr(
                cluster, EZB_ZCL_ATTR_ELECTRICAL_MEASUREMENT_DC_CURRENT_MULTIPLIER_ID, &multiplier) != EZB_ERR_NONE ||
            ezb_zcl_electrical_measurement_cluster_desc_add_attr(
                cluster, EZB_ZCL_ATTR_ELECTRICAL_MEASUREMENT_DC_CURRENT_DIVISOR_ID, &divisor) != EZB_ERR_NONE) {
            return EZB_INVALID_ZCL_CLUSTER_DESC;
        }
    }
    return cluster;
}

static ezb_zcl_cluster_desc_t zigbee_create_measurement_cluster(hugo_sensor_kind_t kind) {
    switch (kind) {
        case HUGO_SENSOR_TEMPERATURE: {
            ezb_zcl_temperature_measurement_cluster_server_config_t config = {
                .measured_value = (int16_t)0x8000,
                .min_measured_value = -27315,
                .max_measured_value = 32767,
            };
            return ezb_zcl_temperature_measurement_create_cluster_desc(&config, EZB_ZCL_CLUSTER_SERVER);
        }
        case HUGO_SENSOR_HUMIDITY: {
            ezb_zcl_rel_humidity_measurement_cluster_server_config_t config = {
                .measured_value = 0xffff,
                .min_measured_value = 0,
                .max_measured_value = 10000,
            };
            return ezb_zcl_rel_humidity_measurement_create_cluster_desc(&config, EZB_ZCL_CLUSTER_SERVER);
        }
        case HUGO_SENSOR_PRESSURE: {
            ezb_zcl_pressure_measurement_cluster_server_config_t config = {
                .measured_value = (int16_t)0x8000,
                .min_measured_value = 0,
                .max_measured_value = 32767,
            };
            return ezb_zcl_pressure_measurement_create_cluster_desc(&config, EZB_ZCL_CLUSTER_SERVER);
        }
        case HUGO_SENSOR_WIND_SPEED: {
            ezb_zcl_wind_speed_measurement_cluster_server_config_t config = {
                .measured_value = 0xffff,
                .min_measured_value = 0,
                .max_measured_value = 0xfffe,
            };
            return ezb_zcl_wind_speed_measurement_create_cluster_desc(&config, EZB_ZCL_CLUSTER_SERVER);
        }
        case HUGO_SENSOR_CO2: {
            ezb_zcl_carbon_dioxide_measurement_cluster_server_config_t config = {
                .measured_value = 0.0f,
                .min_measured_value = 0.0f,
                .max_measured_value = 1.0f,
            };
            return ezb_zcl_carbon_dioxide_measurement_create_cluster_desc(&config, EZB_ZCL_CLUSTER_SERVER);
        }
        default:
            return EZB_INVALID_ZCL_CLUSTER_DESC;
    }
}

static ezb_zcl_cluster_desc_t zigbee_create_environment_cluster(uint8_t endpoint_id) {
    ezb_zcl_custom_cluster_config_t config = {
        .cluster_id = HUGO_ZIGBEE_ENVIRONMENT_CLUSTER,
        .init_func = NULL,
        .deinit_func = NULL,
    };
    ezb_zcl_cluster_desc_t cluster = ezb_zcl_custom_create_cluster_desc(&config, EZB_ZCL_CLUSTER_SERVER);
    if (cluster == EZB_INVALID_ZCL_CLUSTER_DESC) {
        return cluster;
    }
    const uint8_t access = EZB_ZCL_ATTR_ACCESS_READ | EZB_ZCL_ATTR_ACCESS_REPORTING;
    if (zigbee_endpoint_has_sensor(endpoint_id, HUGO_SENSOR_WIND_DIRECTION)) {
        const uint16_t value = 0xffff;
        if (ezb_zcl_custom_cluster_desc_add_attr(
                cluster, HUGO_ZIGBEE_ATTR_WIND_DIRECTION, EZB_ZCL_ATTR_TYPE_UINT16, access, &value) != EZB_ERR_NONE) {
            return EZB_INVALID_ZCL_CLUSTER_DESC;
        }
    }
    if (zigbee_endpoint_has_sensor(endpoint_id, HUGO_SENSOR_RAIN_AMOUNT)) {
        const uint32_t value = 0xffffffff;
        if (ezb_zcl_custom_cluster_desc_add_attr(
                cluster, HUGO_ZIGBEE_ATTR_RAIN_AMOUNT, EZB_ZCL_ATTR_TYPE_UINT32, access, &value) != EZB_ERR_NONE) {
            return EZB_INVALID_ZCL_CLUSTER_DESC;
        }
    }
    return cluster;
}

static ezb_zcl_cluster_desc_t zigbee_create_sensor_cluster(uint8_t endpoint_id, uint16_t cluster_id) {
    if (cluster_id == EZB_ZCL_CLUSTER_ID_ELECTRICAL_MEASUREMENT) {
        return zigbee_create_electrical_cluster(endpoint_id);
    }
    if (cluster_id == HUGO_ZIGBEE_ENVIRONMENT_CLUSTER) {
        return zigbee_create_environment_cluster(endpoint_id);
    }
    for (size_t i = 0; i < zigbee_sensor_count; ++i) {
        if (zigbee_sensors[i].endpoint_id == endpoint_id && zigbee_sensors[i].cluster_id == cluster_id) {
            return zigbee_create_measurement_cluster(zigbee_sensors[i].kind);
        }
    }
    return EZB_INVALID_ZCL_CLUSTER_DESC;
}

static esp_err_t zigbee_add_endpoint(ezb_af_device_desc_t device, uint8_t endpoint_id) {
    ezb_af_ep_config_t endpoint_config = {
        .ep_id = endpoint_id,
        .app_profile_id = EZB_AF_HA_PROFILE_ID,
        .app_device_id = zigbee_endpoint_has_cluster(endpoint_id, EZB_ZCL_CLUSTER_ID_ELECTRICAL_MEASUREMENT)
            ? EZB_ZHA_CONSUMPTION_AWARENESS_DEVICE_ID
            : EZB_ZHA_SIMPLE_SENSOR_DEVICE_ID,
        .app_device_version = 0,
    };
    ezb_af_ep_desc_t endpoint = ezb_af_create_endpoint_desc(&endpoint_config);
    if (endpoint == EZB_INVALID_AF_EP_DESC) {
        return ESP_FAIL;
    }

    ezb_zcl_cluster_desc_t basic = ezb_zcl_basic_create_cluster_desc(NULL, EZB_ZCL_CLUSTER_SERVER);
    ezb_zcl_cluster_desc_t identify = ezb_zcl_identify_create_cluster_desc(NULL, EZB_ZCL_CLUSTER_SERVER);
    if (basic == EZB_INVALID_ZCL_CLUSTER_DESC || identify == EZB_INVALID_ZCL_CLUSTER_DESC ||
        ezb_zcl_basic_cluster_desc_add_attr(
            basic, EZB_ZCL_ATTR_BASIC_MANUFACTURER_NAME_ID, (void *)manufacturer_name) != EZB_ERR_NONE ||
        ezb_zcl_basic_cluster_desc_add_attr(
            basic, EZB_ZCL_ATTR_BASIC_MODEL_IDENTIFIER_ID, (void *)model_identifier) != EZB_ERR_NONE ||
        ezb_af_endpoint_add_cluster_desc(endpoint, basic) != EZB_ERR_NONE ||
        ezb_af_endpoint_add_cluster_desc(endpoint, identify) != EZB_ERR_NONE) {
        return ESP_FAIL;
    }

    for (size_t i = 0; i < zigbee_sensor_count; ++i) {
        hugo_sensor_config_t *sensor = &zigbee_sensors[i];
        if (sensor->endpoint_id != endpoint_id) {
            continue;
        }
        bool first_cluster = true;
        for (size_t previous = 0; previous < i; ++previous) {
            if (zigbee_sensors[previous].endpoint_id == endpoint_id &&
                zigbee_sensors[previous].cluster_id == sensor->cluster_id) {
                first_cluster = false;
                break;
            }
        }
        if (!first_cluster) {
            continue;
        }
        ezb_zcl_cluster_desc_t cluster = zigbee_create_sensor_cluster(endpoint_id, sensor->cluster_id);
        if (cluster == EZB_INVALID_ZCL_CLUSTER_DESC ||
            ezb_af_endpoint_add_cluster_desc(endpoint, cluster) != EZB_ERR_NONE) {
            return ESP_FAIL;
        }
    }
    return ezb_af_device_add_endpoint_desc(device, endpoint) == EZB_ERR_NONE ? ESP_OK : ESP_FAIL;
}

static esp_err_t zigbee_register_sensors(void) {
    if (zigbee_sensor_count == 0) {
        ESP_LOGE(TAG, "No sensors configured; call zigbee.add_sensor() before zigbee.start()");
        return ESP_FAIL;
    }
    ezb_af_device_desc_t device = ezb_af_create_device_desc();
    if (device == EZB_INVALID_AF_DEVICE_DESC) {
        return ESP_FAIL;
    }
    for (size_t i = 0; i < zigbee_sensor_count; ++i) {
        bool first_endpoint = true;
        for (size_t previous = 0; previous < i; ++previous) {
            if (zigbee_sensors[previous].endpoint_id == zigbee_sensors[i].endpoint_id) {
                first_endpoint = false;
                break;
            }
        }
        if (first_endpoint && zigbee_add_endpoint(device, zigbee_sensors[i].endpoint_id) != ESP_OK) {
            return ESP_FAIL;
        }
    }
    return ezb_af_device_desc_register(device) == EZB_ERR_NONE ? ESP_OK : ESP_FAIL;
}

static void zigbee_task(void *arg) {
    (void)arg;
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
    // Diagnostic setting: accept weak parents while joining or rejoining.
    // Raise this threshold after validating the antenna and network topology.
    ezb_nwk_set_min_join_lqi(HUGO_ZIGBEE_MIN_JOIN_LQI);
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
        zigbee_register_sensors() != ESP_OK ||
        esp_zigbee_start(false) != ESP_OK) {
        ESP_LOGE(TAG, "Zigbee setup failed");
        goto done;
    }

    zigbee_ready = true;
    ESP_LOGI(TAG, "Zigbee sensor device started with %u sensor(s)", (unsigned)zigbee_sensor_count);
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
    if (zigbee_sensor_count == 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("call add_sensor before start"));
    }
    if (!zigbee_started) {
        zigbee_startup_signal_seen = false;
        zigbee_initialization_status = -1;
        zigbee_factory_new = -1;
        zigbee_last_steering_status = -1;
        zigbee_steering_in_progress = false;
        zigbee_rejoining = false;
        zigbee_last_error = EZB_ERR_NONE;
        zigbee_started = true;
        if (xTaskCreate(zigbee_task, "hugo_zigbee", 6144, NULL, 5, NULL) != pdPASS) {
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
    mp_obj_dict_store(status, MP_OBJ_NEW_QSTR(MP_QSTR_steering_in_progress), mp_obj_new_bool(zigbee_steering_in_progress));
    mp_obj_dict_store(status, MP_OBJ_NEW_QSTR(MP_QSTR_rejoining), mp_obj_new_bool(zigbee_rejoining));
    mp_obj_dict_store(status, MP_OBJ_NEW_QSTR(MP_QSTR_startup_seen), mp_obj_new_bool(zigbee_startup_signal_seen));
    mp_obj_dict_store(status, MP_OBJ_NEW_QSTR(MP_QSTR_initialization_status), mp_obj_new_int(zigbee_initialization_status));
    mp_obj_dict_store(status, MP_OBJ_NEW_QSTR(MP_QSTR_factory_new), mp_obj_new_int(zigbee_factory_new));
    mp_obj_dict_store(status, MP_OBJ_NEW_QSTR(MP_QSTR_steering_status), mp_obj_new_int(zigbee_last_steering_status));
    mp_obj_dict_store(status, MP_OBJ_NEW_QSTR(MP_QSTR_last_error), mp_obj_new_int(zigbee_last_error));
    return status;
}
static MP_DEFINE_CONST_FUN_OBJ_0(zigbee_status_obj, zigbee_status);

static mp_obj_t zigbee_join(void) {
    if (!zigbee_ready) {
        mp_raise_OSError(MP_ENODEV);
    }
    if (zigbee_rejoining) {
        return mp_const_none;
    }
    if (zigbee_initialization_status != EZB_BDB_STATUS_SUCCESS) {
        mp_raise_OSError(MP_EAGAIN);
    }
    if (!zigbee_joined && !zigbee_steering_in_progress) {
        if (!esp_zigbee_lock_acquire(pdMS_TO_TICKS(1000))) {
            mp_raise_OSError(MP_ETIMEDOUT);
        }
        ezb_err_t result = ezb_bdb_start_top_level_commissioning(EZB_BDB_MODE_NETWORK_STEERING);
        esp_zigbee_lock_release();
        if (result == EZB_ERR_NONE || result == EZB_ERR_BUSY) {
            zigbee_steering_in_progress = true;
            zigbee_last_steering_status = -1;
            return mp_const_none;
        }
        zigbee_last_error = result;
        if (result != EZB_ERR_NONE) {
            mp_raise_OSError(MP_EIO);
        }
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(zigbee_join_obj, zigbee_join);

static mp_obj_t zigbee_factory_reset(void) {
    if (!zigbee_ready) {
        mp_raise_OSError(MP_ENODEV);
    }
    if (!esp_zigbee_lock_acquire(pdMS_TO_TICKS(1000))) {
        mp_raise_OSError(MP_ETIMEDOUT);
    }
    ESP_LOGW(TAG, "Erasing Zigbee network data and restarting");
    esp_zigbee_factory_reset();
}
static MP_DEFINE_CONST_FUN_OBJ_0(zigbee_factory_reset_obj, zigbee_factory_reset);

static const char *zigbee_sensor_unit(hugo_sensor_kind_t kind) {
    static const char *units[] = {"V", "mA", "deg C", "%", "hPa", "m/s", "ppm", "deg", "mm"};
    return units[kind];
}

static mp_float_t zigbee_sensor_resolution(hugo_sensor_kind_t kind) {
    if (kind == HUGO_SENSOR_DC_CURRENT) {
        return 0.1;
    }
    if (kind == HUGO_SENSOR_PRESSURE) {
        return 1.0;
    }
    return 0.01;
}

static hugo_sensor_kind_t zigbee_get_sensor_kind(uint16_t cluster_id, int attribute_id) {
    if (cluster_id == EZB_ZCL_CLUSTER_ID_ELECTRICAL_MEASUREMENT) {
        if (attribute_id == EZB_ZCL_ATTR_ELECTRICAL_MEASUREMENT_DC_VOLTAGE_ID) {
            return HUGO_SENSOR_DC_VOLTAGE;
        }
        if (attribute_id == EZB_ZCL_ATTR_ELECTRICAL_MEASUREMENT_DC_CURRENT_ID) {
            return HUGO_SENSOR_DC_CURRENT;
        }
        mp_raise_ValueError(MP_ERROR_TEXT("electrical measurement requires DC_VOLTAGE or DC_CURRENT"));
    }
    if (cluster_id == HUGO_ZIGBEE_ENVIRONMENT_CLUSTER) {
        if (attribute_id == -1 || attribute_id == HUGO_ZIGBEE_ATTR_WIND_DIRECTION) {
            return HUGO_SENSOR_WIND_DIRECTION;
        }
        if (attribute_id == HUGO_ZIGBEE_ATTR_RAIN_AMOUNT) {
            return HUGO_SENSOR_RAIN_AMOUNT;
        }
        mp_raise_ValueError(MP_ERROR_TEXT("environment measurement requires WIND_DIRECTION or RAIN_AMOUNT"));
    }
    if (attribute_id != -1 && attribute_id != 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("unsupported attribute_id"));
    }
    switch (cluster_id) {
        case EZB_ZCL_CLUSTER_ID_TEMPERATURE_MEASUREMENT:
            return HUGO_SENSOR_TEMPERATURE;
        case EZB_ZCL_CLUSTER_ID_REL_HUMIDITY_MEASUREMENT:
            return HUGO_SENSOR_HUMIDITY;
        case EZB_ZCL_CLUSTER_ID_PRESSURE_MEASUREMENT:
            return HUGO_SENSOR_PRESSURE;
        case EZB_ZCL_CLUSTER_ID_WIND_SPEED_MEASUREMENT:
            return HUGO_SENSOR_WIND_SPEED;
        case EZB_ZCL_CLUSTER_ID_CARBON_DIOXIDE_MEASUREMENT:
            return HUGO_SENSOR_CO2;
        default:
            mp_raise_ValueError(MP_ERROR_TEXT("unsupported cluster_id"));
    }
}

static mp_obj_t zigbee_add_sensor(size_t n_args, const mp_obj_t *pos_args, mp_map_t *kw_args) {
    enum { ARG_cluster_id, ARG_attribute_id, ARG_endpoint_id };
    static const mp_arg_t allowed_args[] = {
        { MP_QSTR_cluster_id, MP_ARG_REQUIRED | MP_ARG_INT, {.u_int = 0} },
        { MP_QSTR_attribute_id, MP_ARG_INT, {.u_int = -1} },
        { MP_QSTR_endpoint_id, MP_ARG_KW_ONLY | MP_ARG_INT, {.u_int = 0} },
    };
    mp_arg_val_t args[MP_ARRAY_SIZE(allowed_args)];
    mp_arg_parse_all(n_args, pos_args, kw_args, MP_ARRAY_SIZE(allowed_args), allowed_args, args);

    if (zigbee_started) {
        mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("cannot add sensors after start"));
    }
    int cluster_arg = args[ARG_cluster_id].u_int;
    int attribute_arg = args[ARG_attribute_id].u_int;
    int endpoint_arg = args[ARG_endpoint_id].u_int;
    if (cluster_arg < 0 || cluster_arg > UINT16_MAX || attribute_arg < -1 || attribute_arg > UINT16_MAX) {
        mp_raise_ValueError(MP_ERROR_TEXT("cluster_id and attribute_id must be uint16"));
    }
    uint16_t cluster_id = cluster_arg;
    hugo_sensor_kind_t kind = zigbee_get_sensor_kind(cluster_id, attribute_arg);
    uint16_t attribute_id = attribute_arg == -1 ? 0 : attribute_arg;
    int endpoint_id_arg = endpoint_arg == 0
        ? (cluster_id == EZB_ZCL_CLUSTER_ID_ELECTRICAL_MEASUREMENT
            ? HUGO_ZIGBEE_ELECTRICAL_ENDPOINT
            : HUGO_ZIGBEE_WEATHER_ENDPOINT)
        : endpoint_arg;
    if (endpoint_id_arg < 1 || endpoint_id_arg > 240) {
        mp_raise_ValueError(MP_ERROR_TEXT("endpoint_id must be 1..240"));
    }
    uint8_t endpoint_id = endpoint_id_arg;

    size_t sensor_index = zigbee_sensor_count;
    for (size_t i = 0; i < zigbee_sensor_count; ++i) {
        if (zigbee_sensors[i].endpoint_id == endpoint_id &&
            zigbee_sensors[i].cluster_id == cluster_id &&
            zigbee_sensors[i].attribute_id == attribute_id) {
            sensor_index = i;
            break;
        }
    }
    if (sensor_index == zigbee_sensor_count) {
        if (zigbee_sensor_count == HUGO_ZIGBEE_MAX_SENSORS) {
            mp_raise_ValueError(MP_ERROR_TEXT("too many sensors"));
        }
        zigbee_sensors[sensor_index] = (hugo_sensor_config_t) {
            .endpoint_id = endpoint_id,
            .cluster_id = cluster_id,
            .attribute_id = attribute_id,
            .kind = kind,
        };
        ++zigbee_sensor_count;
    }

    hugo_sensor_obj_t *sensor = mp_obj_malloc(hugo_sensor_obj_t, &zigbee_sensor_type);
    sensor->sensor_index = sensor_index;
    return MP_OBJ_FROM_PTR(sensor);
}
static MP_DEFINE_CONST_FUN_OBJ_KW(zigbee_add_sensor_obj, 1, zigbee_add_sensor);

static int32_t zigbee_round(mp_float_t value) {
    return (int32_t)(value >= 0 ? value + 0.5 : value - 0.5);
}

static mp_obj_t zigbee_sensor_send(mp_obj_t self_in, mp_obj_t value_in) {
    hugo_sensor_obj_t *self = MP_OBJ_TO_PTR(self_in);
    hugo_sensor_config_t *sensor = &zigbee_sensors[self->sensor_index];
    mp_float_t value = mp_obj_get_float(value_in);
    union {
        int16_t i16;
        uint16_t u16;
        uint32_t u32;
        float f32;
    } encoded;

    switch (sensor->kind) {
        case HUGO_SENSOR_DC_VOLTAGE:
            if (!(value >= 3.0 && value <= 5.0)) {
                mp_raise_ValueError(MP_ERROR_TEXT("voltage outside 3..5 V"));
            }
            encoded.i16 = zigbee_round(value * 100.0);
            break;
        case HUGO_SENSOR_DC_CURRENT:
            if (!(value >= 0.1 && value <= 1000.0)) {
                mp_raise_ValueError(MP_ERROR_TEXT("current outside 0.1..1000 mA"));
            }
            encoded.i16 = zigbee_round(value * 10.0);
            break;
        case HUGO_SENSOR_TEMPERATURE:
            if (!(value >= -273.15 && value <= 327.67)) {
                mp_raise_ValueError(MP_ERROR_TEXT("temperature outside -273.15..327.67 C"));
            }
            encoded.i16 = zigbee_round(value * 100.0);
            break;
        case HUGO_SENSOR_HUMIDITY:
            if (!(value >= 0.0 && value <= 100.0)) {
                mp_raise_ValueError(MP_ERROR_TEXT("humidity outside 0..100 %"));
            }
            encoded.u16 = zigbee_round(value * 100.0);
            break;
        case HUGO_SENSOR_PRESSURE:
            if (!(value >= 0.0 && value <= 32767.0)) {
                mp_raise_ValueError(MP_ERROR_TEXT("pressure outside 0..32767 hPa"));
            }
            encoded.i16 = zigbee_round(value);
            break;
        case HUGO_SENSOR_WIND_SPEED:
            if (!(value >= 0.0 && value <= 655.34)) {
                mp_raise_ValueError(MP_ERROR_TEXT("wind speed outside 0..655.34 m/s"));
            }
            encoded.u16 = zigbee_round(value * 100.0);
            break;
        case HUGO_SENSOR_CO2:
            if (!(value >= 0.0 && value <= 1000000.0)) {
                mp_raise_ValueError(MP_ERROR_TEXT("CO2 outside 0..1000000 ppm"));
            }
            encoded.f32 = value / 1000000.0;
            break;
        case HUGO_SENSOR_WIND_DIRECTION:
            if (!(value >= 0.0 && value < 360.0)) {
                mp_raise_ValueError(MP_ERROR_TEXT("wind direction must be in [0, 360) degrees"));
            }
            encoded.u16 = zigbee_round(value * 100.0);
            break;
        case HUGO_SENSOR_RAIN_AMOUNT:
            if (!(value >= 0.0 && value <= 42949672.95)) {
                mp_raise_ValueError(MP_ERROR_TEXT("rain amount outside uint32 range"));
            }
            encoded.u32 = (uint32_t)(value * 100.0 + 0.5);
            break;
    }

    if (!zigbee_ready || !zigbee_joined) {
        mp_raise_OSError(MP_ENOTCONN);
    }
    ezb_zcl_report_attr_cmd_t report = {
        .cmd_ctrl = {
            .fc.direction = EZB_ZCL_CMD_DIRECTION_TO_CLI,
            .dst_addr.addr_mode = EZB_ADDR_MODE_NONE,
            .src_ep = sensor->endpoint_id,
            .cluster_id = sensor->cluster_id,
        },
        .payload = {
            .attr_id = sensor->attribute_id,
        },
    };
    if (!esp_zigbee_lock_acquire(pdMS_TO_TICKS(1000))) {
        mp_raise_OSError(MP_ETIMEDOUT);
    }
    ezb_zcl_status_t update = ezb_zcl_set_attr_value(
        sensor->endpoint_id, sensor->cluster_id, EZB_ZCL_CLUSTER_SERVER,
        sensor->attribute_id, EZB_ZCL_STD_MANUF_CODE, &encoded, false);
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
static MP_DEFINE_CONST_FUN_OBJ_2(zigbee_sensor_send_obj, zigbee_sensor_send);

static void zigbee_sensor_attr(mp_obj_t self_in, qstr attr, mp_obj_t *dest) {
    if (dest[0] != MP_OBJ_NULL) {
        return;
    }
    hugo_sensor_obj_t *self = MP_OBJ_TO_PTR(self_in);
    hugo_sensor_config_t *sensor = &zigbee_sensors[self->sensor_index];
    if (attr == MP_QSTR_endpoint_id) {
        dest[0] = mp_obj_new_int(sensor->endpoint_id);
    } else if (attr == MP_QSTR_cluster_id) {
        dest[0] = mp_obj_new_int(sensor->cluster_id);
    } else if (attr == MP_QSTR_attribute_id) {
        dest[0] = mp_obj_new_int(sensor->attribute_id);
    } else if (attr == MP_QSTR_role) {
        dest[0] = mp_obj_new_str("server", 6);
    } else if (attr == qstr_from_str("unit")) {
        const char *unit = zigbee_sensor_unit(sensor->kind);
        dest[0] = mp_obj_new_str(unit, strlen(unit));
    } else if (attr == MP_QSTR_resolution) {
        dest[0] = mp_obj_new_float(zigbee_sensor_resolution(sensor->kind));
    } else {
        dest[1] = MP_OBJ_SENTINEL;
    }
}

static void zigbee_sensor_print(const mp_print_t *print, mp_obj_t self_in, mp_print_kind_t kind) {
    (void)kind;
    hugo_sensor_obj_t *self = MP_OBJ_TO_PTR(self_in);
    hugo_sensor_config_t *sensor = &zigbee_sensors[self->sensor_index];
    mp_printf(print, "Sensor(endpoint_id=%u, cluster_id=0x%04x, attribute_id=0x%04x, unit='%s')",
        sensor->endpoint_id, sensor->cluster_id, sensor->attribute_id, zigbee_sensor_unit(sensor->kind));
}

static const mp_rom_map_elem_t zigbee_sensor_locals_table[] = {
    { MP_ROM_QSTR(MP_QSTR_send), MP_ROM_PTR(&zigbee_sensor_send_obj) },
};
static MP_DEFINE_CONST_DICT(zigbee_sensor_locals, zigbee_sensor_locals_table);

MP_DEFINE_CONST_OBJ_TYPE(
    zigbee_sensor_type,
    MP_QSTR_Sensor,
    MP_TYPE_FLAG_NONE,
    print, zigbee_sensor_print,
    attr, zigbee_sensor_attr,
    locals_dict, &zigbee_sensor_locals
    );

static mp_obj_t zigbee_set_temperature(mp_obj_t temperature_obj) {
    for (size_t i = 0; i < zigbee_sensor_count; ++i) {
        if (zigbee_sensors[i].kind == HUGO_SENSOR_TEMPERATURE) {
            hugo_sensor_obj_t sensor = {
                .base = { &zigbee_sensor_type },
                .sensor_index = i,
            };
            return zigbee_sensor_send(MP_OBJ_FROM_PTR(&sensor), temperature_obj);
        }
    }
    mp_raise_ValueError(MP_ERROR_TEXT("temperature sensor is not configured"));
}
static MP_DEFINE_CONST_FUN_OBJ_1(zigbee_set_temperature_obj, zigbee_set_temperature);

static const mp_rom_map_elem_t zigbee_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_zigbee) },
    { MP_ROM_QSTR(MP_QSTR_Sensor), MP_ROM_PTR(&zigbee_sensor_type) },
    { MP_ROM_QSTR(MP_QSTR_start), MP_ROM_PTR(&zigbee_start_obj) },
    { MP_ROM_QSTR(MP_QSTR_joined), MP_ROM_PTR(&zigbee_is_joined_obj) },
    { MP_ROM_QSTR(MP_QSTR_status), MP_ROM_PTR(&zigbee_status_obj) },
    { MP_ROM_QSTR(MP_QSTR_join), MP_ROM_PTR(&zigbee_join_obj) },
    { MP_ROM_QSTR(MP_QSTR_factory_reset), MP_ROM_PTR(&zigbee_factory_reset_obj) },
    { MP_ROM_QSTR(MP_QSTR_add_sensor), MP_ROM_PTR(&zigbee_add_sensor_obj) },
    { MP_ROM_QSTR(MP_QSTR_set_temperature), MP_ROM_PTR(&zigbee_set_temperature_obj) },
    { MP_ROM_QSTR(MP_QSTR_ELECTRICAL_ENDPOINT), MP_ROM_INT(HUGO_ZIGBEE_ELECTRICAL_ENDPOINT) },
    { MP_ROM_QSTR(MP_QSTR_WEATHER_ENDPOINT), MP_ROM_INT(HUGO_ZIGBEE_WEATHER_ENDPOINT) },
    { MP_ROM_QSTR(MP_QSTR_ELECTRICAL_MEASUREMENT), MP_ROM_INT(EZB_ZCL_CLUSTER_ID_ELECTRICAL_MEASUREMENT) },
    { MP_ROM_QSTR(MP_QSTR_DC_VOLTAGE), MP_ROM_INT(EZB_ZCL_ATTR_ELECTRICAL_MEASUREMENT_DC_VOLTAGE_ID) },
    { MP_ROM_QSTR(MP_QSTR_DC_CURRENT), MP_ROM_INT(EZB_ZCL_ATTR_ELECTRICAL_MEASUREMENT_DC_CURRENT_ID) },
    { MP_ROM_QSTR(MP_QSTR_TEMPERATURE_MEASUREMENT), MP_ROM_INT(EZB_ZCL_CLUSTER_ID_TEMPERATURE_MEASUREMENT) },
    { MP_ROM_QSTR(MP_QSTR_RELATIVE_HUMIDITY_MEASUREMENT), MP_ROM_INT(EZB_ZCL_CLUSTER_ID_REL_HUMIDITY_MEASUREMENT) },
    { MP_ROM_QSTR(MP_QSTR_PRESSURE_MEASUREMENT), MP_ROM_INT(EZB_ZCL_CLUSTER_ID_PRESSURE_MEASUREMENT) },
    { MP_ROM_QSTR(MP_QSTR_WIND_SPEED_MEASUREMENT), MP_ROM_INT(EZB_ZCL_CLUSTER_ID_WIND_SPEED_MEASUREMENT) },
    { MP_ROM_QSTR(MP_QSTR_CO2_MEASUREMENT), MP_ROM_INT(EZB_ZCL_CLUSTER_ID_CARBON_DIOXIDE_MEASUREMENT) },
    { MP_ROM_QSTR(MP_QSTR_ENVIRONMENT_MEASUREMENT), MP_ROM_INT(HUGO_ZIGBEE_ENVIRONMENT_CLUSTER) },
    { MP_ROM_QSTR(MP_QSTR_MEASURED_VALUE), MP_ROM_INT(0x0000) },
    { MP_ROM_QSTR(MP_QSTR_WIND_DIRECTION), MP_ROM_INT(HUGO_ZIGBEE_ATTR_WIND_DIRECTION) },
    { MP_ROM_QSTR(MP_QSTR_RAIN_AMOUNT), MP_ROM_INT(HUGO_ZIGBEE_ATTR_RAIN_AMOUNT) },
};
static MP_DEFINE_CONST_DICT(zigbee_globals, zigbee_globals_table);

const mp_obj_module_t zigbee_module = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&zigbee_globals,
};
MP_REGISTER_MODULE(MP_QSTR_zigbee, zigbee_module);
