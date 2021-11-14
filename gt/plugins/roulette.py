import copy
from enum import Enum
import json
import os
from os import path
from pathlib import Path
import random

from nonebot import on_command, CommandSession
from nonebot.log import logger
from aiocqhttp import MessageSegment

import config
from gt.utilities import util
