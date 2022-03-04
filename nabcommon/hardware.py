import platform


def device_model():
    """
    Return effective device model if running on Raspberry Pi hardware,
    generic platform identification otherwise
    """
    try:
        with open("/proc/device-tree/model") as model_f:
            model = model_f.readline()
    except (FileNotFoundError):
        model = platform.platform()
    return model
