from ast import literal_eval
import os, pathlib
import pandas
import config
import random
import numpy
import json

from datetime import timedelta
from datetime import datetime
from pytz import timezone
from nonebot import on_command, CommandSession
from os import path
from nonebot import on_natural_language, NLPSession, IntentCommand
from nonebot.log import logger

from gt.utilities.util import TIME_ZONE, current_time, Category, string_to_date_translator, date_to_string_translator
from aiocqhttp import MessageSegment
from gt.plugins import gacha

# Food menu file. 
# Read-only file. 
# Manully add new food in the file.
FOOD_FILE = path.join(config.INTERNAL_DATA_DIR, 'list', 'foodMenu.csv')
FOOD_INFO = pandas.read_csv(FOOD_FILE, encoding='utf-8')
FOOD_HISTORY_FILE = path.join(config.DATA_DIR, 'gacha', 'foodHistory.csv')
FOOD_NAMES = FOOD_INFO['Name'].values
FOOD_SCORES = FOOD_INFO['Score'].values
USER_DATA_DIR = path.join(config.DATA_DIR, 'gacha')
USER_DATA_FILE = path.join(USER_DATA_DIR, 'users.json')
CAI_JIAO_NAMES = FOOD_INFO.loc[FOOD_INFO['Category'] == Category.BELL_PEPPER.name]['Name'].values

WHAT_TO_EAT_ALIAS = ('今天吃什么','有什么吃的','吃什么啊','吃什么',)
WINDOW_BREAK_STATS_ALIAS = ('今天打玻璃了吗', '今天玻璃碎了吗', '玻璃碎了吗', '玻璃')
NO_WINDOW_BREAK_MESSAGE = ['没有啊，玻璃是好的','应该没有吧','公主今天很听话，玻璃还是好的',
                            '公主出去玩了，应该还好','我还没看，应该是好的吧']
WINDOW_BREAK_MESSAGE = ['有的！今天吃彩椒！','看着桌上的彩椒你就懂了','今天是彩椒大餐哦','公主跑了，要不你把窗户修了吧，哼哼',
                        '刚好，你去把公主抓回来吃彩椒',]
NOT_ENOUGH_CRYSTAL_MESSAGE = ['你水晶不够，吃屁','就你这小水晶，嘿嘿','都是大鹏摘的，你这水晶哪儿够啊','我看你是真的不懂哦']
ADD_FOOD_SUCCESS_MESSAGE = ['哼，这次就多做一点吧','不知道小公主知道了会是什么心情呢','谢谢老板！下次再来哦']

@on_command('小公主今天吃什么', aliases=WHAT_TO_EAT_ALIAS, only_to_me=False)
async def what_to_eat_today(session: CommandSession):
    food_menu = food_today()
    await session.send('今天有{}'.format(', '.join(food_menu)))
    return

@on_command('小公主今天打玻璃了吗', aliases=WINDOW_BREAK_STATS_ALIAS, only_to_me=False)
async def break_window_today(session: CommandSession):
    if(window_break_found_out() is 'True'):
        message = random.choice(WINDOW_BREAK_MESSAGE)
    else:
        message = random.choice(NO_WINDOW_BREAK_MESSAGE)
    await session.send(message)

@on_command('加餐', only_to_me=False)
async def add_food(session: CommandSession):
    user_id = session.event['user_id']
    user_id_str = str(user_id)
    server = 'cn'
    current_date_str = date_to_string_translator(current_time(), True)
    user_data = gacha.read_user_data()
    gacha.initialize_user_server_data(user_data, user_id, server)
    total_crystal = user_data[user_id_str][server]['crystals']
    food_history_info = pandas.read_csv(FOOD_HISTORY_FILE, encoding='utf-8', index_col=0)
    food_menu = food_today()

    arg_str = session.current_arg_text.strip()
    if arg_str not in FOOD_NAMES:
        await session.send('你这{}我做不了啊，现在能做{}'.format(arg_str, ', '.join(FOOD_NAMES)))
        return

    if arg_str in food_menu:
        message = '今天已经吃了{}了。今天吃了{}'.format(arg_str, ', '.join(food_menu))
        await session.send(message)
        return

    food_crystal = int(FOOD_INFO.loc[FOOD_INFO['Name'] == arg_str]['Crystal'].values[0])
    if food_crystal > total_crystal:
        await session.send(f'要{food_crystal}个水晶，{random.choice(NOT_ENOUGH_CRYSTAL_MESSAGE)}')
        return

    # Add food to history.
    old_menu_name = literal_eval(food_history_info.loc[food_history_info['Date'] == current_date_str]['Name'].values[0])
    old_menu_name.append(arg_str)
    food_history_info.loc[food_history_info['Date'] == current_date_str, 'Name'] = str(old_menu_name)

    old_menu_add = literal_eval(food_history_info.loc[food_history_info['Date'] == current_date_str]['Add'].values[0])
    old_menu_add.setdefault(user_id_str,[]).append(arg_str)
    food_history_info.loc[food_history_info['Date'] == current_date_str, 'Add'] = str(old_menu_add)

    # Use crystals.
    user_data[user_id_str][server]['crystals'] -= food_crystal

    # Save data.
    food_history_info.to_csv(FOOD_HISTORY_FILE)
    gacha.save_user_data(user_data)

    info_message = '你花了{}给小公主加餐，还剩{}。 '.format(food_crystal, user_data[user_id_str][server]['crystals'])

    await session.send(info_message + random.choice(ADD_FOOD_SUCCESS_MESSAGE))


@on_natural_language(keywords={'给小公主加个'}, only_to_me=False)
async def _(session: NLPSession):
    stripped_msg = session.msg_text.strip()
    return IntentCommand(90.0, '加餐', current_arg=stripped_msg[6:])

@on_natural_language(keywords={'来一份'}, only_to_me=False)
async def _(session: NLPSession):
    stripped_msg = session.msg_text.strip()
    return IntentCommand(90.0, '加餐', current_arg=stripped_msg[3:])

# Generates food for today and store it in the food menu.
def generateFood(current_date_str: str):
    sum_food_scores = sum(FOOD_SCORES)
    normalized_prob = [food_score / sum_food_scores for food_score in FOOD_SCORES]
    food_today = numpy.random.choice(
        FOOD_NAMES,
        size = 5,
        replace = False,
        p = normalized_prob).tolist()

    break_window = bool(random.getrandbits(1))
    break_window_found_out = ((random.random() < 0.2) and break_window)

    cai_jiao_toady = random.choice(CAI_JIAO_NAMES)


    if (break_window_found_out and cai_jiao_toady not in food_today):
        food_today.append(cai_jiao_toady)

    df = pandas.DataFrame([
        [current_date_str, food_today, str(break_window), str(break_window_found_out), {}]
    ])
    df.to_csv(FOOD_HISTORY_FILE, index=True, mode='a', header=False)

# Gets the food menu today.
def food_today():
    current_date_str = date_to_string_translator(current_time(), True)

    food_history_info = pandas.read_csv(FOOD_HISTORY_FILE, encoding='utf-8')
    if current_date_str not in food_history_info['Date'].values:
        generateFood(current_date_str)
    food_history_info = pandas.read_csv(FOOD_HISTORY_FILE, encoding='utf-8')
    return literal_eval(food_history_info.loc[food_history_info['Date'] == current_date_str]['Name'].values[0])


# Gets the window status.
def window_break_found_out():
    current_date_str = date_to_string_translator(current_time(), True)

    food_history_info = pandas.read_csv(FOOD_HISTORY_FILE, encoding='utf-8')
    if current_date_str not in food_history_info['Date'].values:
        generateFood(current_date_str)
    food_history_info = pandas.read_csv(FOOD_HISTORY_FILE, encoding='utf-8')
    return food_history_info.loc[food_history_info['Date'] == current_date_str]['WINDOW_BREAK_FOUND_OUT'].values[0]
