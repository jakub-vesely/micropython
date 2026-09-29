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
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "py/mperrno.h"
#include "py/obj.h"
#include "py/runtime.h"

#define ZIGBEE_MAX_ENDPOINTS 8
#define ZIGBEE_MAX_CLUSTERS 24
#define ZIGBEE_MAX_ATTRIBUTES 48
#define ZIGBEE_NAME_MAX 31
#define ZIGBEE_REPORT_CONFIRM_TIMEOUT_MS 3000

typedef union {
    uint8_t u8;
    uint16_t u16;
    uint32_t u32;
    int8_t i8;
    int16_t i16;
    int32_t i32;
    float f32;
} zigbee_value_t;

typedef struct {
    uint8_t endpoint_id;
    uint16_t profile_id;
    uint16_t device_id;
    uint8_t device_version;
} zigbee_endpoint_config_t;

typedef struct {
    uint8_t endpoint_index;
    uint16_t cluster_id;
    uint8_t role;
} zigbee_cluster_config_t;

typedef struct {
    uint8_t cluster_index;
    uint16_t attribute_id;
    uint8_t data_type;
    uint8_t access;
    uint16_t manufacturer_code;
    zigbee_value_t value;
} zigbee_attribute_config_t;

typedef struct { mp_obj_base_t base; uint8_t index; } zigbee_config_obj_t;

typedef struct {
    SemaphoreHandle_t done;
    volatile uint8_t status;
    volatile uint8_t references;
} zigbee_report_confirmation_t;

static const char *TAG = "hugo_zigbee";
static uint8_t zigbee_manufacturer[ZIGBEE_NAME_MAX + 2] = "\x04" "HuGo";
static uint8_t zigbee_model[ZIGBEE_NAME_MAX + 2] = "\x07" CONFIG_IDF_TARGET;
static uint32_t zigbee_primary_channels = (1U << 13);
static uint32_t zigbee_secondary_channels = 0x07fff800U;
static uint8_t zigbee_min_join_lqi;

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
static volatile ezb_err_t zigbee_last_report_error = EZB_ERR_NONE;
static SemaphoreHandle_t zigbee_report_mutex;
static esp_timer_handle_t zigbee_init_retry_timer;
static zigbee_endpoint_config_t zigbee_endpoints[ZIGBEE_MAX_ENDPOINTS];
static zigbee_cluster_config_t zigbee_clusters[ZIGBEE_MAX_CLUSTERS];
static zigbee_attribute_config_t zigbee_attributes[ZIGBEE_MAX_ATTRIBUTES];
static size_t zigbee_endpoint_count;
static size_t zigbee_cluster_count;
static size_t zigbee_attribute_count;

extern const mp_obj_type_t zigbee_endpoint_type;
extern const mp_obj_type_t zigbee_cluster_type;
extern const mp_obj_type_t zigbee_attribute_type;

static void zigbee_report_confirmation_release(zigbee_report_confirmation_t *confirmation) {
    if (__atomic_sub_fetch(&confirmation->references, 1, __ATOMIC_ACQ_REL) == 0) {
        vSemaphoreDelete(confirmation->done);
        vPortFree(confirmation);
    }
}

static void zigbee_report_confirmed(ezb_zcl_cmd_cnf_t *confirmation, void *user_ctx) {
    zigbee_report_confirmation_t *pending = user_ctx;
    __atomic_store_n(&pending->status, confirmation->status, __ATOMIC_RELEASE);
    zigbee_last_report_error = confirmation->status;
    xSemaphoreGive(pending->done);
    zigbee_report_confirmation_release(pending);
}

static bool zigbee_report_sync_init(void) {
    if (zigbee_report_mutex != NULL) {
        return true;
    }
    zigbee_report_mutex = xSemaphoreCreateMutex();
    return zigbee_report_mutex != NULL;
}

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

static ezb_zcl_cluster_desc_t zigbee_create_cluster(const zigbee_cluster_config_t *config) {
    switch (config->cluster_id) {
        case EZB_ZCL_CLUSTER_ID_ELECTRICAL_MEASUREMENT:
            return ezb_zcl_electrical_measurement_create_cluster_desc(NULL, config->role);
        case EZB_ZCL_CLUSTER_ID_TEMPERATURE_MEASUREMENT:
            return ezb_zcl_temperature_measurement_create_cluster_desc(NULL, config->role);
        case EZB_ZCL_CLUSTER_ID_REL_HUMIDITY_MEASUREMENT:
            return ezb_zcl_rel_humidity_measurement_create_cluster_desc(NULL, config->role);
        case EZB_ZCL_CLUSTER_ID_PRESSURE_MEASUREMENT:
            return ezb_zcl_pressure_measurement_create_cluster_desc(NULL, config->role);
        case EZB_ZCL_CLUSTER_ID_WIND_SPEED_MEASUREMENT:
            return ezb_zcl_wind_speed_measurement_create_cluster_desc(NULL, config->role);
        case EZB_ZCL_CLUSTER_ID_CARBON_DIOXIDE_MEASUREMENT:
            return ezb_zcl_carbon_dioxide_measurement_create_cluster_desc(NULL, config->role);
        default:
            if (config->cluster_id >= EZB_ZCL_CLUSTER_ID_MIN_CUSTOM) {
                ezb_zcl_custom_cluster_config_t custom = {
                    .cluster_id = config->cluster_id,
                    .init_func = NULL,
                    .deinit_func = NULL,
                };
                return ezb_zcl_custom_create_cluster_desc(&custom, config->role);
            }
            return EZB_INVALID_ZCL_CLUSTER_DESC;
    }
}

static esp_err_t zigbee_apply_attribute(ezb_zcl_cluster_desc_t cluster, zigbee_attribute_config_t *attribute) {
    ezb_zcl_attr_desc_t desc = ezb_zcl_cluster_get_attr_desc(
        cluster, attribute->attribute_id, attribute->manufacturer_code);
    if (desc != EZB_INVALID_ZCL_ATTR_DESC) {
        if (ezb_zcl_attr_desc_get_type(desc) != attribute->data_type ||
            ezb_zcl_attr_desc_set_access(desc, attribute->access) != EZB_ERR_NONE ||
            ezb_zcl_attr_desc_set_value(desc, &attribute->value) != EZB_ERR_NONE) {
            return ESP_FAIL;
        }
        return ESP_OK;
    }
    desc = ezb_zcl_create_attr_desc(attribute->attribute_id, attribute->data_type,
        attribute->access, attribute->manufacturer_code, &attribute->value);
    return desc != EZB_INVALID_ZCL_ATTR_DESC &&
        ezb_zcl_cluster_add_attr_desc(cluster, desc) == EZB_ERR_NONE ? ESP_OK : ESP_FAIL;
}

static esp_err_t zigbee_register_endpoint(ezb_af_device_desc_t device, size_t endpoint_index) {
    zigbee_endpoint_config_t *config = &zigbee_endpoints[endpoint_index];
    ezb_af_ep_config_t endpoint_config = {
        .ep_id = config->endpoint_id,
        .app_profile_id = config->profile_id,
        .app_device_id = config->device_id,
        .app_device_version = config->device_version,
    };
    ezb_af_ep_desc_t endpoint = ezb_af_create_endpoint_desc(&endpoint_config);
    if (endpoint == EZB_INVALID_AF_EP_DESC) {
        return ESP_FAIL;
    }

    ezb_zcl_cluster_desc_t basic = ezb_zcl_basic_create_cluster_desc(NULL, EZB_ZCL_CLUSTER_SERVER);
    ezb_zcl_cluster_desc_t identify = ezb_zcl_identify_create_cluster_desc(NULL, EZB_ZCL_CLUSTER_SERVER);
    if (basic == EZB_INVALID_ZCL_CLUSTER_DESC || identify == EZB_INVALID_ZCL_CLUSTER_DESC ||
        ezb_zcl_basic_cluster_desc_add_attr(
            basic, EZB_ZCL_ATTR_BASIC_MANUFACTURER_NAME_ID, zigbee_manufacturer) != EZB_ERR_NONE ||
        ezb_zcl_basic_cluster_desc_add_attr(
            basic, EZB_ZCL_ATTR_BASIC_MODEL_IDENTIFIER_ID, zigbee_model) != EZB_ERR_NONE ||
        ezb_af_endpoint_add_cluster_desc(endpoint, basic) != EZB_ERR_NONE ||
        ezb_af_endpoint_add_cluster_desc(endpoint, identify) != EZB_ERR_NONE) {
        return ESP_FAIL;
    }

    for (size_t i = 0; i < zigbee_cluster_count; ++i) {
        zigbee_cluster_config_t *cluster_config = &zigbee_clusters[i];
        if (cluster_config->endpoint_index != endpoint_index) {
            continue;
        }
        ezb_zcl_cluster_desc_t cluster = zigbee_create_cluster(cluster_config);
        if (cluster == EZB_INVALID_ZCL_CLUSTER_DESC) {
            return ESP_FAIL;
        }
        for (size_t j = 0; j < zigbee_attribute_count; ++j) {
            if (zigbee_attributes[j].cluster_index == i &&
                zigbee_apply_attribute(cluster, &zigbee_attributes[j]) != ESP_OK) {
                return ESP_FAIL;
            }
        }
        if (ezb_af_endpoint_add_cluster_desc(endpoint, cluster) != EZB_ERR_NONE) {
            return ESP_FAIL;
        }
    }
    return ezb_af_device_add_endpoint_desc(device, endpoint) == EZB_ERR_NONE ? ESP_OK : ESP_FAIL;
}

static esp_err_t zigbee_register_device(void) {
    if (zigbee_endpoint_count == 0) {
        ESP_LOGE(TAG, "No endpoints configured; call zigbee.add_endpoint() before zigbee.start()");
        return ESP_FAIL;
    }
    ezb_af_device_desc_t device = ezb_af_create_device_desc();
    if (device == EZB_INVALID_AF_DEVICE_DESC) {
        return ESP_FAIL;
    }
    for (size_t i = 0; i < zigbee_endpoint_count; ++i) {
        if (zigbee_register_endpoint(device, i) != ESP_OK) {
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
    ezb_nwk_set_min_join_lqi(zigbee_min_join_lqi);
    esp_timer_create_args_t retry_timer_args = {
        .callback = zigbee_retry_initialization,
        .name = "zigbee_init_retry",
    };
    if (esp_timer_create(&retry_timer_args, &zigbee_init_retry_timer) != ESP_OK) {
        ESP_LOGE(TAG, "Unable to create Zigbee initialization retry timer");
        goto done;
    }
    ezb_aps_secur_enable_distributed_security(false);
    if (ezb_bdb_set_primary_channel_set(zigbee_primary_channels) != EZB_ERR_NONE ||
        ezb_bdb_set_secondary_channel_set(zigbee_secondary_channels) != EZB_ERR_NONE ||
        ezb_app_signal_add_handler(zigbee_signal_handler) != EZB_ERR_NONE ||
        zigbee_register_device() != ESP_OK ||
        esp_zigbee_start(false) != ESP_OK) {
        ESP_LOGE(TAG, "Zigbee setup failed");
        goto done;
    }

    zigbee_ready = true;
    ESP_LOGI(TAG, "Zigbee device started with %u endpoint(s)", (unsigned)zigbee_endpoint_count);
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
    if (zigbee_endpoint_count == 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("call add_endpoint before start"));
    }
    if (!zigbee_started) {
        if (!zigbee_report_sync_init()) {
            mp_raise_OSError(MP_ENOMEM);
        }
        zigbee_startup_signal_seen = false;
        zigbee_initialization_status = -1;
        zigbee_factory_new = -1;
        zigbee_last_steering_status = -1;
        zigbee_steering_in_progress = false;
        zigbee_rejoining = false;
        zigbee_last_error = EZB_ERR_NONE;
        zigbee_last_report_error = EZB_ERR_NONE;
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
    int network_address = -1;
    int pan_id = -1;
    int channel = -1;
    uint64_t ieee_address = 0;
    uint64_t extended_pan_id = 0;
    if (zigbee_ready && esp_zigbee_lock_acquire(pdMS_TO_TICKS(1000))) {
        ezb_extaddr_t ieee;
        ezb_extpanid_t extended_pan;
        ezb_nwk_get_extended_address(&ieee);
        ezb_nwk_get_extended_panid(&extended_pan);
        memcpy(&ieee_address, &ieee, sizeof(ieee_address));
        memcpy(&extended_pan_id, &extended_pan, sizeof(extended_pan_id));
        network_address = ezb_nwk_get_short_address();
        pan_id = ezb_nwk_get_panid();
        channel = ezb_nwk_get_current_channel();
        esp_zigbee_lock_release();
    }
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
    mp_obj_dict_store(status, MP_OBJ_NEW_QSTR(MP_QSTR_last_report_error), mp_obj_new_int(zigbee_last_report_error));
    mp_obj_dict_store(status, MP_OBJ_NEW_QSTR(MP_QSTR_network_address), mp_obj_new_int(network_address));
    mp_obj_dict_store(status, MP_OBJ_NEW_QSTR(MP_QSTR_pan_id), mp_obj_new_int(pan_id));
    mp_obj_dict_store(status, MP_OBJ_NEW_QSTR(MP_QSTR_channel), mp_obj_new_int(channel));
    mp_obj_dict_store(status, MP_OBJ_NEW_QSTR(MP_QSTR_ieee_address), mp_obj_new_int_from_ull(ieee_address));
    mp_obj_dict_store(status, MP_OBJ_NEW_QSTR(MP_QSTR_extended_pan_id), mp_obj_new_int_from_ull(extended_pan_id));
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

static void zigbee_store_name(uint8_t *target, mp_obj_t value) {
    size_t length;
    const char *text = mp_obj_str_get_data(value, &length);
    if (length > ZIGBEE_NAME_MAX) {
        mp_raise_ValueError(MP_ERROR_TEXT("name too long"));
    }
    target[0] = length;
    memcpy(target + 1, text, length);
}

static void zigbee_store_value(zigbee_attribute_config_t *attribute, mp_obj_t value) {
    mp_int_t integer;
    switch (attribute->data_type) {
        case EZB_ZCL_ATTR_TYPE_BOOL:
        case EZB_ZCL_ATTR_TYPE_UINT8:
            integer = mp_obj_get_int(value);
            if (integer < 0 || integer > UINT8_MAX) mp_raise_ValueError(MP_ERROR_TEXT("value outside uint8"));
            attribute->value.u8 = integer;
            break;
        case EZB_ZCL_ATTR_TYPE_UINT16:
            integer = mp_obj_get_int(value);
            if (integer < 0 || integer > UINT16_MAX) mp_raise_ValueError(MP_ERROR_TEXT("value outside uint16"));
            attribute->value.u16 = integer;
            break;
        case EZB_ZCL_ATTR_TYPE_UINT32:
        case EZB_ZCL_ATTR_TYPE_MAP32:
            attribute->value.u32 = mp_obj_get_int_truncated(value);
            break;
        case EZB_ZCL_ATTR_TYPE_INT8:
            integer = mp_obj_get_int(value);
            if (integer < INT8_MIN || integer > INT8_MAX) mp_raise_ValueError(MP_ERROR_TEXT("value outside int8"));
            attribute->value.i8 = integer;
            break;
        case EZB_ZCL_ATTR_TYPE_INT16:
            integer = mp_obj_get_int(value);
            if (integer < INT16_MIN || integer > INT16_MAX) mp_raise_ValueError(MP_ERROR_TEXT("value outside int16"));
            attribute->value.i16 = integer;
            break;
        case EZB_ZCL_ATTR_TYPE_INT32:
            attribute->value.i32 = mp_obj_get_int(value);
            break;
        case EZB_ZCL_ATTR_TYPE_SINGLE:
            attribute->value.f32 = mp_obj_get_float(value);
            break;
        default:
            mp_raise_ValueError(MP_ERROR_TEXT("unsupported ZCL data type"));
    }
}

static mp_obj_t zigbee_configure(size_t n_args, const mp_obj_t *pos_args, mp_map_t *kw_args) {
    enum { ARG_manufacturer, ARG_model, ARG_primary_channels, ARG_secondary_channels, ARG_min_join_lqi };
    static const mp_arg_t allowed[] = {
        { MP_QSTR_manufacturer, MP_ARG_OBJ, {.u_obj = MP_OBJ_NULL} },
        { MP_QSTR_model, MP_ARG_OBJ, {.u_obj = MP_OBJ_NULL} },
        { MP_QSTR_primary_channels, MP_ARG_INT, {.u_int = 1U << 13} },
        { MP_QSTR_secondary_channels, MP_ARG_INT, {.u_int = 0x07fff800U} },
        { MP_QSTR_min_join_lqi, MP_ARG_INT, {.u_int = 0} },
    };
    if (zigbee_started) mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("cannot configure after start"));
    mp_arg_val_t args[MP_ARRAY_SIZE(allowed)];
    mp_arg_parse_all(n_args, pos_args, kw_args, MP_ARRAY_SIZE(allowed), allowed, args);
    if (args[ARG_manufacturer].u_obj != MP_OBJ_NULL) zigbee_store_name(zigbee_manufacturer, args[ARG_manufacturer].u_obj);
    if (args[ARG_model].u_obj != MP_OBJ_NULL) zigbee_store_name(zigbee_model, args[ARG_model].u_obj);
    zigbee_primary_channels = args[ARG_primary_channels].u_int;
    zigbee_secondary_channels = args[ARG_secondary_channels].u_int;
    int lqi = args[ARG_min_join_lqi].u_int;
    if (lqi < 0 || lqi > UINT8_MAX) mp_raise_ValueError(MP_ERROR_TEXT("min_join_lqi must be 0..255"));
    zigbee_min_join_lqi = lqi;
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_KW(zigbee_configure_obj, 0, zigbee_configure);

static mp_obj_t zigbee_add_endpoint(size_t n_args, const mp_obj_t *pos_args, mp_map_t *kw_args) {
    enum { ARG_endpoint_id, ARG_profile_id, ARG_device_id, ARG_device_version };
    static const mp_arg_t allowed[] = {
        { MP_QSTR_endpoint_id, MP_ARG_REQUIRED | MP_ARG_INT, {.u_int = 0} },
        { MP_QSTR_profile_id, MP_ARG_KW_ONLY | MP_ARG_INT, {.u_int = EZB_AF_HA_PROFILE_ID} },
        { MP_QSTR_device_id, MP_ARG_KW_ONLY | MP_ARG_INT, {.u_int = EZB_ZHA_SIMPLE_SENSOR_DEVICE_ID} },
        { MP_QSTR_device_version, MP_ARG_KW_ONLY | MP_ARG_INT, {.u_int = 0} },
    };
    if (zigbee_started) mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("cannot add endpoints after start"));
    mp_arg_val_t args[MP_ARRAY_SIZE(allowed)];
    mp_arg_parse_all(n_args, pos_args, kw_args, MP_ARRAY_SIZE(allowed), allowed, args);
    int id = args[ARG_endpoint_id].u_int;
    if (id < 1 || id > 240 || zigbee_endpoint_count == ZIGBEE_MAX_ENDPOINTS) mp_raise_ValueError(MP_ERROR_TEXT("invalid or too many endpoints"));
    size_t index = zigbee_endpoint_count++;
    zigbee_endpoints[index] = (zigbee_endpoint_config_t) { id, args[ARG_profile_id].u_int,
        args[ARG_device_id].u_int, args[ARG_device_version].u_int };
    zigbee_config_obj_t *obj = mp_obj_malloc(zigbee_config_obj_t, &zigbee_endpoint_type);
    obj->index = index;
    return MP_OBJ_FROM_PTR(obj);
}
static MP_DEFINE_CONST_FUN_OBJ_KW(zigbee_add_endpoint_obj, 1, zigbee_add_endpoint);

static mp_obj_t zigbee_endpoint_add_cluster(size_t n_args, const mp_obj_t *pos_args, mp_map_t *kw_args) {
    enum { ARG_cluster_id, ARG_role };
    static const mp_arg_t allowed[] = {
        { MP_QSTR_cluster_id, MP_ARG_REQUIRED | MP_ARG_INT, {.u_int = 0} },
        { MP_QSTR_role, MP_ARG_KW_ONLY | MP_ARG_INT, {.u_int = EZB_ZCL_CLUSTER_SERVER} },
    };
    zigbee_config_obj_t *self = MP_OBJ_TO_PTR(pos_args[0]);
    mp_arg_val_t args[MP_ARRAY_SIZE(allowed)];
    mp_arg_parse_all(n_args - 1, pos_args + 1, kw_args, MP_ARRAY_SIZE(allowed), allowed, args);
    if (zigbee_started || zigbee_cluster_count == ZIGBEE_MAX_CLUSTERS) mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("cannot add cluster"));
    size_t index = zigbee_cluster_count++;
    zigbee_clusters[index] = (zigbee_cluster_config_t) { self->index, args[ARG_cluster_id].u_int, args[ARG_role].u_int };
    zigbee_config_obj_t *obj = mp_obj_malloc(zigbee_config_obj_t, &zigbee_cluster_type);
    obj->index = index;
    return MP_OBJ_FROM_PTR(obj);
}
static MP_DEFINE_CONST_FUN_OBJ_KW(zigbee_endpoint_add_cluster_obj, 2, zigbee_endpoint_add_cluster);

static mp_obj_t zigbee_cluster_add_attribute(size_t n_args, const mp_obj_t *pos_args, mp_map_t *kw_args) {
    enum { ARG_attribute_id, ARG_data_type, ARG_initial, ARG_access, ARG_manufacturer_code };
    static const mp_arg_t allowed[] = {
        { MP_QSTR_attribute_id, MP_ARG_REQUIRED | MP_ARG_INT, {.u_int = 0} },
        { MP_QSTR_data_type, MP_ARG_REQUIRED | MP_ARG_INT, {.u_int = 0} },
        { MP_QSTR_initial, MP_ARG_REQUIRED | MP_ARG_OBJ, {.u_obj = MP_OBJ_NULL} },
        { MP_QSTR_access, MP_ARG_KW_ONLY | MP_ARG_INT, {.u_int = EZB_ZCL_ATTR_ACCESS_READ | EZB_ZCL_ATTR_ACCESS_REPORTING} },
        { MP_QSTR_manufacturer_code, MP_ARG_KW_ONLY | MP_ARG_INT, {.u_int = EZB_ZCL_STD_MANUF_CODE} },
    };
    zigbee_config_obj_t *self = MP_OBJ_TO_PTR(pos_args[0]);
    mp_arg_val_t args[MP_ARRAY_SIZE(allowed)];
    mp_arg_parse_all(n_args - 1, pos_args + 1, kw_args, MP_ARRAY_SIZE(allowed), allowed, args);
    if (zigbee_started || zigbee_attribute_count == ZIGBEE_MAX_ATTRIBUTES) mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("cannot add attribute"));
    size_t index = zigbee_attribute_count++;
    zigbee_attribute_config_t *attribute = &zigbee_attributes[index];
    *attribute = (zigbee_attribute_config_t) { .cluster_index = self->index,
        .attribute_id = args[ARG_attribute_id].u_int, .data_type = args[ARG_data_type].u_int,
        .access = args[ARG_access].u_int, .manufacturer_code = args[ARG_manufacturer_code].u_int };
    zigbee_store_value(attribute, args[ARG_initial].u_obj);
    zigbee_config_obj_t *obj = mp_obj_malloc(zigbee_config_obj_t, &zigbee_attribute_type);
    obj->index = index;
    return MP_OBJ_FROM_PTR(obj);
}
static MP_DEFINE_CONST_FUN_OBJ_KW(zigbee_cluster_add_attribute_obj, 4, zigbee_cluster_add_attribute);

static mp_obj_t zigbee_attribute_send(mp_obj_t self_in, mp_obj_t value_in) {
    zigbee_config_obj_t *self = MP_OBJ_TO_PTR(self_in);
    zigbee_attribute_config_t *attribute = &zigbee_attributes[self->index];
    zigbee_cluster_config_t *cluster = &zigbee_clusters[attribute->cluster_index];
    zigbee_endpoint_config_t *endpoint = &zigbee_endpoints[cluster->endpoint_index];
    zigbee_store_value(attribute, value_in);
    if (!zigbee_ready || !zigbee_joined) mp_raise_OSError(MP_ENOTCONN);
    if (zigbee_report_mutex == NULL) mp_raise_OSError(MP_ENODEV);

    zigbee_report_confirmation_t *confirmation = pvPortMalloc(sizeof(*confirmation));
    if (confirmation == NULL) mp_raise_OSError(MP_ENOMEM);
    confirmation->done = xSemaphoreCreateBinary();
    if (confirmation->done == NULL) {
        vPortFree(confirmation);
        mp_raise_OSError(MP_ENOMEM);
    }
    confirmation->status = UINT8_MAX;
    confirmation->references = 2;

    if (xSemaphoreTake(zigbee_report_mutex, pdMS_TO_TICKS(ZIGBEE_REPORT_CONFIRM_TIMEOUT_MS)) != pdTRUE) {
        confirmation->references = 1;
        zigbee_report_confirmation_release(confirmation);
        zigbee_last_report_error = EZB_ERR_TIMEOUT;
        return mp_const_false;
    }

    ezb_zcl_report_attr_cmd_t report = {
        .cmd_ctrl = {
            .fc.direction = EZB_ZCL_CMD_DIRECTION_TO_CLI,
            .dst_addr.addr_mode = EZB_ADDR_MODE_NONE,
            .src_ep = endpoint->endpoint_id,
            .cluster_id = cluster->cluster_id,
            .cnf_ctx = {
                .cb = zigbee_report_confirmed,
                .user_ctx = confirmation,
            },
        },
        .payload = {
            .attr_id = attribute->attribute_id,
        },
    };
    if (!esp_zigbee_lock_acquire(pdMS_TO_TICKS(1000))) {
        confirmation->references = 1;
        zigbee_report_confirmation_release(confirmation);
        xSemaphoreGive(zigbee_report_mutex);
        mp_raise_OSError(MP_ETIMEDOUT);
    }
    ezb_zcl_status_t update = ezb_zcl_set_attr_value(
        endpoint->endpoint_id, cluster->cluster_id, cluster->role,
        attribute->attribute_id, attribute->manufacturer_code, &attribute->value, false);
    ezb_err_t send = EZB_ERR_NONE;
    if (update == EZB_ZCL_STATUS_SUCCESS) {
        zigbee_last_report_error = EZB_ERR_NONE;
        send = ezb_zcl_report_attr_cmd_req(&report);
    }
    esp_zigbee_lock_release();
    if (update != EZB_ZCL_STATUS_SUCCESS) {
        confirmation->references = 1;
        zigbee_report_confirmation_release(confirmation);
        xSemaphoreGive(zigbee_report_mutex);
        ESP_LOGE(TAG, "Unable to update endpoint %u cluster 0x%04x attribute 0x%04x: 0x%02x",
            endpoint->endpoint_id, cluster->cluster_id, attribute->attribute_id, update);
        mp_raise_OSError(MP_EIO);
    }
    if (send != EZB_ERR_NONE) {
        zigbee_last_report_error = send;
        confirmation->references = 1;
        zigbee_report_confirmation_release(confirmation);
        xSemaphoreGive(zigbee_report_mutex);
        ESP_LOGW(TAG,
            "Attribute updated, but report request failed: 0x%x",
            send);
        return mp_const_false;
    }

    bool completed = xSemaphoreTake(
        confirmation->done, pdMS_TO_TICKS(ZIGBEE_REPORT_CONFIRM_TIMEOUT_MS)) == pdTRUE;
    uint8_t status = completed
        ? __atomic_load_n(&confirmation->status, __ATOMIC_ACQUIRE)
        : UINT8_MAX;
    if (!completed) {
        zigbee_last_report_error = EZB_ERR_TIMEOUT;
        ESP_LOGW(TAG, "Attribute report confirmation timed out");
    } else if (status != EZB_ZCL_STATUS_SUCCESS) {
        zigbee_last_report_error = status;
        ESP_LOGW(TAG, "Attribute report delivery failed: 0x%02x", status);
    } else {
        zigbee_last_report_error = EZB_ERR_NONE;
    }
    zigbee_report_confirmation_release(confirmation);
    xSemaphoreGive(zigbee_report_mutex);
    return mp_obj_new_bool(completed && status == EZB_ZCL_STATUS_SUCCESS);
}
static MP_DEFINE_CONST_FUN_OBJ_2(zigbee_attribute_send_obj, zigbee_attribute_send);

static const mp_rom_map_elem_t zigbee_endpoint_locals_table[] = {
    { MP_ROM_QSTR(MP_QSTR_add_cluster), MP_ROM_PTR(&zigbee_endpoint_add_cluster_obj) },
};
static MP_DEFINE_CONST_DICT(zigbee_endpoint_locals, zigbee_endpoint_locals_table);
MP_DEFINE_CONST_OBJ_TYPE(zigbee_endpoint_type, MP_QSTR_Endpoint, MP_TYPE_FLAG_NONE,
    locals_dict, &zigbee_endpoint_locals);

static const mp_rom_map_elem_t zigbee_cluster_locals_table[] = {
    { MP_ROM_QSTR(MP_QSTR_add_attribute), MP_ROM_PTR(&zigbee_cluster_add_attribute_obj) },
};
static MP_DEFINE_CONST_DICT(zigbee_cluster_locals, zigbee_cluster_locals_table);
MP_DEFINE_CONST_OBJ_TYPE(zigbee_cluster_type, MP_QSTR_Cluster, MP_TYPE_FLAG_NONE,
    locals_dict, &zigbee_cluster_locals);

static const mp_rom_map_elem_t zigbee_attribute_locals_table[] = {
    { MP_ROM_QSTR(MP_QSTR_send), MP_ROM_PTR(&zigbee_attribute_send_obj) },
};
static MP_DEFINE_CONST_DICT(zigbee_attribute_locals, zigbee_attribute_locals_table);
MP_DEFINE_CONST_OBJ_TYPE(zigbee_attribute_type, MP_QSTR_Attribute, MP_TYPE_FLAG_NONE,
    locals_dict, &zigbee_attribute_locals);

static const mp_rom_map_elem_t zigbee_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_zigbee) },
    { MP_ROM_QSTR(MP_QSTR_Endpoint), MP_ROM_PTR(&zigbee_endpoint_type) },
    { MP_ROM_QSTR(MP_QSTR_Cluster), MP_ROM_PTR(&zigbee_cluster_type) },
    { MP_ROM_QSTR(MP_QSTR_Attribute), MP_ROM_PTR(&zigbee_attribute_type) },
    { MP_ROM_QSTR(MP_QSTR_configure), MP_ROM_PTR(&zigbee_configure_obj) },
    { MP_ROM_QSTR(MP_QSTR_add_endpoint), MP_ROM_PTR(&zigbee_add_endpoint_obj) },
    { MP_ROM_QSTR(MP_QSTR_start), MP_ROM_PTR(&zigbee_start_obj) },
    { MP_ROM_QSTR(MP_QSTR_joined), MP_ROM_PTR(&zigbee_is_joined_obj) },
    { MP_ROM_QSTR(MP_QSTR_status), MP_ROM_PTR(&zigbee_status_obj) },
    { MP_ROM_QSTR(MP_QSTR_join), MP_ROM_PTR(&zigbee_join_obj) },
    { MP_ROM_QSTR(MP_QSTR_factory_reset), MP_ROM_PTR(&zigbee_factory_reset_obj) },
    { MP_ROM_QSTR(MP_QSTR_HA_PROFILE), MP_ROM_INT(EZB_AF_HA_PROFILE_ID) },
    { MP_ROM_QSTR(MP_QSTR_SIMPLE_SENSOR), MP_ROM_INT(EZB_ZHA_SIMPLE_SENSOR_DEVICE_ID) },
    { MP_ROM_QSTR(MP_QSTR_CONSUMPTION_AWARENESS), MP_ROM_INT(EZB_ZHA_CONSUMPTION_AWARENESS_DEVICE_ID) },
    { MP_ROM_QSTR(MP_QSTR_SERVER), MP_ROM_INT(EZB_ZCL_CLUSTER_SERVER) },
    { MP_ROM_QSTR(MP_QSTR_CLIENT), MP_ROM_INT(EZB_ZCL_CLUSTER_CLIENT) },
    { MP_ROM_QSTR(MP_QSTR_READ), MP_ROM_INT(EZB_ZCL_ATTR_ACCESS_READ) },
    { MP_ROM_QSTR(MP_QSTR_WRITE), MP_ROM_INT(EZB_ZCL_ATTR_ACCESS_WRITE) },
    { MP_ROM_QSTR(MP_QSTR_REPORTING), MP_ROM_INT(EZB_ZCL_ATTR_ACCESS_REPORTING) },
    { MP_ROM_QSTR(MP_QSTR_BOOL), MP_ROM_INT(EZB_ZCL_ATTR_TYPE_BOOL) },
    { MP_ROM_QSTR(MP_QSTR_UINT8), MP_ROM_INT(EZB_ZCL_ATTR_TYPE_UINT8) },
    { MP_ROM_QSTR(MP_QSTR_UINT16), MP_ROM_INT(EZB_ZCL_ATTR_TYPE_UINT16) },
    { MP_ROM_QSTR(MP_QSTR_UINT32), MP_ROM_INT(EZB_ZCL_ATTR_TYPE_UINT32) },
    { MP_ROM_QSTR(MP_QSTR_MAP32), MP_ROM_INT(EZB_ZCL_ATTR_TYPE_MAP32) },
    { MP_ROM_QSTR(MP_QSTR_INT8), MP_ROM_INT(EZB_ZCL_ATTR_TYPE_INT8) },
    { MP_ROM_QSTR(MP_QSTR_INT16), MP_ROM_INT(EZB_ZCL_ATTR_TYPE_INT16) },
    { MP_ROM_QSTR(MP_QSTR_INT32), MP_ROM_INT(EZB_ZCL_ATTR_TYPE_INT32) },
    { MP_ROM_QSTR(MP_QSTR_FLOAT32), MP_ROM_INT(EZB_ZCL_ATTR_TYPE_SINGLE) },
    { MP_ROM_QSTR(MP_QSTR_ELECTRICAL_MEASUREMENT), MP_ROM_INT(EZB_ZCL_CLUSTER_ID_ELECTRICAL_MEASUREMENT) },
    { MP_ROM_QSTR(MP_QSTR_DC_VOLTAGE), MP_ROM_INT(EZB_ZCL_ATTR_ELECTRICAL_MEASUREMENT_DC_VOLTAGE_ID) },
    { MP_ROM_QSTR(MP_QSTR_DC_CURRENT), MP_ROM_INT(EZB_ZCL_ATTR_ELECTRICAL_MEASUREMENT_DC_CURRENT_ID) },
    { MP_ROM_QSTR(MP_QSTR_TEMPERATURE_MEASUREMENT), MP_ROM_INT(EZB_ZCL_CLUSTER_ID_TEMPERATURE_MEASUREMENT) },
    { MP_ROM_QSTR(MP_QSTR_RELATIVE_HUMIDITY_MEASUREMENT), MP_ROM_INT(EZB_ZCL_CLUSTER_ID_REL_HUMIDITY_MEASUREMENT) },
    { MP_ROM_QSTR(MP_QSTR_PRESSURE_MEASUREMENT), MP_ROM_INT(EZB_ZCL_CLUSTER_ID_PRESSURE_MEASUREMENT) },
    { MP_ROM_QSTR(MP_QSTR_WIND_SPEED_MEASUREMENT), MP_ROM_INT(EZB_ZCL_CLUSTER_ID_WIND_SPEED_MEASUREMENT) },
    { MP_ROM_QSTR(MP_QSTR_CO2_MEASUREMENT), MP_ROM_INT(EZB_ZCL_CLUSTER_ID_CARBON_DIOXIDE_MEASUREMENT) },
};
static MP_DEFINE_CONST_DICT(zigbee_globals, zigbee_globals_table);

const mp_obj_module_t zigbee_module = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&zigbee_globals,
};
MP_REGISTER_MODULE(MP_QSTR_zigbee, zigbee_module);
