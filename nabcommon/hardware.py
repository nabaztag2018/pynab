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


def is_pi_zero(model):
    """
    Return True if given device model is a Raspberry Pi Zero / Zero 2,
    False otherwise
    """
    if "Raspberry Pi Zero" in model:
        # Pi Zero or Zero 2 hardware
        return True
    else:
        # other hardware
        return False
