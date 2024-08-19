include("$(PORT_DIR)/boards/manifest.py")
freeze("modules")
freeze("externals", "ssd1306.py", True)
freeze("externals", "vl53l1x.py", True)
freeze("externals/mpu9250", "ak8963.py", True)
freeze("externals/mpu9250", "mpu6500.py", True)
freeze("externals/mpu9250", "mpu9250.py", True)
freeze("externals/BME280", "bme280_float.py", True)