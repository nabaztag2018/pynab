"""
Serialize & unserialize RFID application data
"""
import re, json

def serialize(email, subject):
    subject.replace("/", "-")
    formatted = email + "/" + subject
    return formatted


def unserialize(data):
    splitted = data.split("/")
    if len(splitted) != 2:
        return None
    email, subject = splitted

    return email, subject

def read_data_ui_text(uid):
    
    f = open("/home/pi/pynab/madb.txt", "r")
    json_str = f.read()
    f.close()
     
    print(json_str)
    
    try:
        uid_data_base=json.loads(json_str)
    except Exception as err:
        print(err)
        uid_data_base={}

    print(uid_data_base)
    
    if uid in uid_data_base:
        record = uid_data_base[uid]
        email, subject = unserialize(record)
    else:
        email, subject = ("default email","default subject")

    return (email,subject)

def write_data_ui_text(uid, email, subject):
    
    f = open("/home/pi/pynab/madb.txt", "r")
    json_str = f.read()
    f.close()
            
    try:
        uid_data_base=json.loads(json_str)
    except Exception as err:
        uid_data_base={}

    data_ser = serialize(email, subject)
    uid_data_base[uid]=data_ser
    json_str=json.dumps(uid_data_base)
    
    f = open("/home/pi/pynab/madb.txt", "w")
    json_str = f.write(json_str)
    f.close()


async def read_data_ui(uid):
    
    from . import models
    config = await models.Config.load_async()
    
    try:
        uid_data_base=json.loads(config.json_data_base)
    except Exception as err:
        uid_data_base=[]
    
    if uid in uid_data_base:
        record = uid_data_base[uid]
        email, subject = unserialize(record)
    else:
        email, subject = ("","")

    return (email,subject)

async def write_data_ui(uid, email, subject):
    from . import models
    config = await models.Config.load_async()
    
    try:
        uid_data_base=json.loads(config.json_data_base)
    except Exception as err:
        uid_data_base={}

    data_ser = serialize(email, subject)
    uid_data_base[uid]=data_ser
    config.json_data_base=json.dumps(uid_data_base)
    await config.save_async()


def read_data_ui_for_views(uid):
    
    from .models import Config
    config = Config.load()
    
    try:
        uid_data_base=json.loads(config.json_data_base)
    except Exception as err:
        uid_data_base=[]
    
    if uid in uid_data_base:
        record = uid_data_base[uid]
        email, subject = unserialize(record)
    else:
        email, subject = ("","")

    return (email,subject)

def write_data_ui_for_views(uid, email, subject):
    from .models import Config
    config = Config.load()
    
    try:
        uid_data_base=json.loads(config.json_data_base)
    except Exception as err:
        uid_data_base={}

    data_ser = serialize(email, subject)
    uid_data_base[uid]=data_ser
    config.json_data_base=json.dumps(uid_data_base)
    config.save()


