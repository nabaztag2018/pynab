"""
Serialize & unserialize RFID application data
"""
import json


async def read_data_ui(uid):

    from . import models

    config = await models.Config.load_async()

    try:
        uid_data_base = json.loads(config.json_data_base)
    except Exception:
        uid_data_base = []

    if uid in uid_data_base:
        event_name = uid_data_base[uid]
    else:
        event_name = "NO_EVENT_NAME"

    return event_name


async def write_data_ui(uid, event_name):
    from . import models

    config = await models.Config.load_async()

    try:
        uid_data_base = json.loads(config.json_data_base)
    except Exception:
        uid_data_base = {}

    uid_data_base[uid] = event_name
    config.json_data_base = json.dumps(uid_data_base)
    await config.save_async()


def read_data_ui_for_views(uid):

    from .models import Config

    config = Config.load()

    try:
        uid_data_base = json.loads(config.json_data_base)
    except Exception:
        uid_data_base = []

    if uid in uid_data_base:
        event_name = uid_data_base[uid]
    else:
        event_name = ""

    return event_name


def write_data_ui_for_views(uid, event_name):
    from .models import Config

    config = Config.load()

    try:
        uid_data_base = json.loads(config.json_data_base)
    except Exception:
        uid_data_base = {}

    uid_data_base[uid] = event_name
    config.json_data_base = json.dumps(uid_data_base)
    config.save()
