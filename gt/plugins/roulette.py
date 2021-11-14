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

ROULETTE_NUM_BULLET_DEFAULT = 6
ROULETTE_MAP_NUM_PLAYER_BULLET = { 2:6, 3:6, 4:8, 5:10, 6:6 }
ROULETTE_MAX_PLAYERS = 6
ROULETTE_ALIASES = ('俄罗斯轮盘赌', '参与轮盘赌', '俄罗斯轮盘', '轮盘', '轮', '盘')
ROULETTE_START_ALIASES = ('开')
ROULETTE_PLAYER_TIMEOUT = 20

RouletteFireResult = Enum('RouletteFireResult', ('normal', 'failure', 'retarget', 'explode'))
ROULETTE_FIRE_RESULT_WEIGHT = {
    RouletteFireResult.normal:    100,
    RouletteFireResult.failure:   3,
    RouletteFireResult.retarget:  6,
    RouletteFireResult.explode:   3
}

class RouletteState:
    def __init__(self):
        self.in_game = False
        self.player_ids = []
        self.next_player_index = 0
        self.next_bullet_index = 0
        self.bullet_index = random.randint(0, ROULETTE_NUM_BULLET_DEFAULT - 1)
        self.player_timer = None

# A map from group id -> roulette game state.
roulette_group_map = dict()

@on_command('轮盘赌', aliases=ROULETTE_ALIASES, only_to_me=False)
async def roulette_join(session: CommandSession):
    if 'group_id' in session.event:
        group_id = session.event['group_id']
    else:
        return await session.send('请在群聊中使用本命令')
    user_id = session.event['user_id']
    if group_id not in roulette_group_map:
        roulette_group_map[group_id] = RouletteState()
    roulette_state = roulette_group_map[group_id]

    if roulette_state.in_game:
        return await session.send('轮盘赌正在进行！')
    elif user_id in roulette_state.player_ids:
        return await session.send('你已经报名了')
    else:
        roulette_state.player_ids.append(user_id)
        if(len(roulette_state.player_ids) == ROULETTE_MAX_PLAYERS):
            await session.send('报名成功，开始游戏')
            start_roulette(roulette_state)
            await send_roulette_instruction(session, roulette_state)
        else:
            await session.send(f'报名成功，当前共{len(roulette_state.player_ids)}人')


@on_command('开始', aliases=ROULETTE_START_ALIASES, only_to_me=False)
async def roulette_start(session: CommandSession):
    if 'group_id' in session.event:
        group_id = session.event['group_id']
    else:
        return
    user_id = session.event['user_id']
    if group_id not in roulette_group_map:
        roulette_group_map[group_id] = RouletteState()
    roulette_state = roulette_group_map[group_id]

    if roulette_state.in_game:
        return await session.send('轮盘赌正在进行！')
    elif user_id not in roulette_state.player_ids:
        return await session.send('你还没报名')
    elif len(roulette_state.player_ids) not in ROULETTE_MAP_NUM_PLAYER_BULLET:
        return await session.send('人数不够开始还')
    else:
        msg = []
        msg.append('好，开始！')
        if len(roulette_state.player_ids) in (4, 5):
            msg.append(f'弹匣容量为{ROULETTE_MAP_NUM_PLAYER_BULLET[len(roulette_state.player_ids)]}')
        await session.send('\n'.join(msg))
        start_roulette(roulette_state)
        await send_roulette_instruction(session, roulette_state)



@on_command('开枪', only_to_me=False)
async def roulette_fire(session: CommandSession):
    if 'group_id' in session.event:
        group_id = session.event['group_id']
    else:
        return
    user_id = session.event['user_id']
    if group_id not in roulette_group_map:
        roulette_group_map[group_id] = RouletteState()
    roulette_state = roulette_group_map[group_id]

    if not roulette_state.in_game:
        return
    elif user_id not in roulette_state.player_ids:
        return
    elif roulette_state.next_player_index != roulette_state.player_ids.index(user_id):
        return await session.send('没到你')
    else:
        if roulette_state.player_timer is not None:
            roulette_state.player_timer.cancel()
        await roulette_fire_event(session, roulette_state)
    

def start_roulette(roulette_state: RouletteState):
    roulette_state.next_player_index = 0
    roulette_state.bullet_index = random.randint(0, ROULETTE_MAP_NUM_PLAYER_BULLET[len(roulette_state.player_ids)] - 1)
    roulette_state.next_bullet_index = 0
    roulette_state.in_game = True

def end_roulette(roulette_state: RouletteState):
    roulette_state.in_game = False
    roulette_state.player_ids = []

def next_roulette(roulette_state: RouletteState):
    roulette_state.next_player_index = (roulette_state.next_player_index + 1) % len(roulette_state.player_ids)
    roulette_state.next_bullet_index += 1

async def roulette_fire_event(session: CommandSession, roulette_state: RouletteState):
    if roulette_state.next_bullet_index == roulette_state.bullet_index:
        fire_result = random.choices(
            population=list(ROULETTE_FIRE_RESULT_WEIGHT.keys()),
            weights=ROULETTE_FIRE_RESULT_WEIGHT.values()
        )[0]

        if fire_result == RouletteFireResult.failure:
            await session.send(random.choice(['这颗唯一的子弹居然卡壳了！没人死', '枪响了！但是没人死']))
        elif fire_result == RouletteFireResult.retarget:
            other_targets = copy.deepcopy(roulette_state.player_ids)
            other_targets.remove(roulette_state.player_ids[roulette_state.next_player_index])
            if len(other_targets) == 0:
                await session.send('枪响了！但是不小心手抖了，没有人死')
            else:
                await session.send(f'枪响了！但是不小心手抖把{MessageSegment.at(random.choice(other_targets))}射死了！')
        elif fire_result == RouletteFireResult.explode:
            await session.send(random.choice(['子弹发生了剧烈的爆炸！！！所有参与的玩家都被炸死了！！！']))
        else:
            await session.send(random.choice(['枪响了！你死了属于是', '好！你死了', '嘣！你死了']))

        end_roulette(roulette_state)
    else:
        await session.send('什么都没发生')
        next_roulette(roulette_state)
        await send_roulette_instruction(session, roulette_state)

async def roulette_player_timeout_callback(session: CommandSession, roulette_state: RouletteState):
    await session.send(random.choice(['太磨叽了！老娘帮你开枪', '太慢了！我来开枪']))
    await roulette_fire_event(session, roulette_state)

async def send_roulette_instruction(session: CommandSession, roulette_state: RouletteState):
    seg_at = MessageSegment.at(roulette_state.player_ids[roulette_state.next_player_index])
    await session.send(seg_at + '该你开枪了')
    roulette_state.player_timer = util.Timer(ROULETTE_PLAYER_TIMEOUT, roulette_player_timeout_callback, session, roulette_state)
