from os import path

from nonebot.default_config import *

SUPERUSERS = {904340407}
COMMAND_START = {'', '/', '!', '／', '！'}

HOST = "0.0.0.0"
PORT = 3000

DATA_DIR = path.join(path.dirname(__file__), '../gt-bot-data')
INTERNAL_DATA_DIR = path.join(path.dirname(__file__), './gt-bot-data')

CQ_DATA_DIR = path.join(path.dirname(__file__), '../gocqhttp-data')
CQ_MNT_DATA_DIR = '/data'
