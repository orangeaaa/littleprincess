import json
import os
from os import path
from pathlib import Path
import random

from nonebot import on_command, CommandSession
from nonebot.log import logger
from aiocqhttp import MessageSegment

import config
from gt.utilities import chara, resource, util

# User data should be something as follows:
# {
#     "user_id": {
#         "server": {
#             "charas": [/* character names */],
#             "crystals": /* int */,
#             "mileage": /* int */,
#             "10_pull_count": /* int */,
#             "last_10_pull_day": /* int */
#         }
#     }
# }
USER_DATA_DIR = path.join(config.DATA_DIR, 'gacha')
USER_DATA_FILE = path.join(USER_DATA_DIR, 'users.json')

RANK_CRYSTAL_MAP = { 1: 1, 2: 8, 3: 50 }

GACHA_10_ALIASES = ('抽十连', '十连！', '十连抽', '来个十连', '来发十连', '来次十连', '抽个十连', '抽发十连', '抽次十连', '十连扭蛋', '扭蛋十连', '10连', '10连！', '10连抽', '来个10连', '来发10连', '来次10连', '抽个10连', '抽发10连', '抽次10连', '10连扭蛋', '扭蛋10连')
USER_GACHA_10_DAILY_LIMIT = 2
USER_GACHA_100_DAILY_LIMIT = 1
TENCHO_TICKET_COUNT = 300

# Initializations.
if not path.isfile(USER_DATA_FILE):
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    with open(USER_DATA_FILE, 'w') as f:
        json.dump({}, f)


# Pool is a dictionary: name -> weight (probability)
def create_default_pool(server, fei_factor=0.5, mei_factor=0.5, knight_male_factor=0.5, knight_female_factor=0.5, guarantee_2star=False):
    cinfo = chara.CHARA_INFO
    if server in chara.CHARA_SERVER:
        charas = chara.CHARA_SERVER[server]
        num_3 = len(cinfo[(cinfo.name.isin(charas)) & (cinfo.initstar == 3)])
        num_2 = len(cinfo[(cinfo.name.isin(charas)) & (cinfo.initstar == 2)]) - 2 # fei/mei, knight_male/knight_female
        num_1 = len(cinfo[(cinfo.name.isin(charas)) & (cinfo.initstar == 1)])

        weight_tot_3 = 0.0275
        weight_tot_2 = 0.9725 if guarantee_2star else 0.19
        weight_tot_1 = 0.0    if guarantee_2star else 0.7825

        weight_3 = weight_tot_3 / num_3
        weight_2 = weight_tot_2 / num_2
        weight_1 = weight_tot_1 / num_1

        pool = dict()
        for c in charas:
            initstar = cinfo[cinfo.name == c].initstar.values[0]
            if initstar == 3:
                pool[c] = weight_3
            elif initstar == 2:
                if c == "fei":
                    pool[c] = weight_2 * fei_factor
                elif c == "mei":
                    pool[c] = weight_2 * mei_factor
                elif c == "knight_male":
                    pool[c] = weight_2 * knight_male_factor
                elif c == "knight_female":
                    pool[c] = weight_2 * knight_female_factor
                else:
                    pool[c] = weight_2
            else:
                pool[c] = weight_1

        return pool
    else:
        raise Exception("Invalid server")


@on_command('十连', aliases=GACHA_10_ALIASES, only_to_me=False)
async def gacha_10(session: CommandSession):
    user_id = session.event['user_id']
    user_id_str = str(user_id)
    server = 'cn'

    user_data = read_user_data()
    initialize_user_server_data(user_data, user_id, server)
    user_server_data = user_data[user_id_str][server]

    # Check if the user has used up daily limit.
    now_day = util.current_time().day
    if now_day != user_server_data['last_10_pull_day']:
        user_server_data['last_10_pull_day'] = now_day
        user_server_data['10_pull_count'] = 0

    if user_server_data['10_pull_count'] >= USER_GACHA_10_DAILY_LIMIT:
        await session.send('你今天不能再抽十连了，明天再来！')
        save_user_data(user_data)
        return
    else:
        user_server_data['10_pull_count'] += 1

    res, new_charas, num_crystals, num_mileage_tickets = do_gacha_10(user_data, user_id, server)
    total_num_crystals = user_data[user_id_str][server]['crystals']
    total_num_mileage_tickets = user_data[user_id_str][server]['mileage']

    # Count rank 3.
    rank3_count = sum(1 for r in res if chara.get_chara_rank(r) == 3)
    rank2_count = sum(1 for r in res if chara.get_chara_rank(r) == 2)
    rank1_count = sum(1 for r in res if chara.get_chara_rank(r) == 1)

    # Create at message.
    seg_at = MessageSegment.at(user_id)

    # Create image.
    res_img = chara.combine_chara_thumbnails_with_rank(res)
    seg_img = MessageSegment.image(util.pic2b64(res_img))

    res_text = []

    if len(new_charas) > 0:
        new_chara_names_comb = '，'.join([f'{chara.CHARA_NAME[server][c]}({chara.get_chara_rank(c)}✦)' for c in new_charas])
        res_text.append(f"获得新角色：{new_chara_names_comb}")

    if rank3_count == 0:
        if rank2_count == 1 and rank1_count == 9:
            res_text.append("惨")

    res_text.append(f"水晶{total_num_crystals}（+{num_crystals}）")
    res_text.append(f"井票{total_num_mileage_tickets}（+{num_mileage_tickets}）")
    res_text_comb = '\n'.join(res_text)

    res = f"{seg_at}\n{seg_img}\n{res_text_comb}"

    # Write user data.
    save_user_data(user_data)

    await session.send(res)

@on_command('一百连', only_to_me=False)
async def gacha_100(session: CommandSession):
    user_id = session.event['user_id']
    user_id_str = str(user_id)
    server = 'cn'

    user_data = read_user_data()
    initialize_user_server_data(user_data, user_id, server)
    user_server_data = user_data[user_id_str][server]

    # Check if the user has used up daily limit.
    now_day = util.current_time().day
    if now_day != user_server_data['last_100_pull_day']:
        user_server_data['last_100_pull_day'] = now_day
        user_server_data['100_pull_count'] = 0

    if user_server_data['100_pull_count'] >= USER_GACHA_100_DAILY_LIMIT:
        await session.send('你今天不能再抽一百连了！')
        save_user_data(user_data)
        return
    else:
        user_server_data['100_pull_count'] += 1

    res, new_charas, num_crystals, num_mileage_tickets = do_gacha_100(user_data, user_id, server)
    total_num_crystals = user_data[user_id_str][server]['crystals']
    total_num_mileage_tickets = user_data[user_id_str][server]['mileage']

    # Count rank 3.
    rank3_count = sum(1 for r in res if chara.get_chara_rank(r) == 3)
    rank2_count = sum(1 for r in res if chara.get_chara_rank(r) == 2)
    rank1_count = sum(1 for r in res if chara.get_chara_rank(r) == 1)

    # Create at message.
    seg_at = MessageSegment.at(user_id)

    # Create image.
    res_img = chara.combine_chara_thumbnails_with_rank(res)
    seg_img = MessageSegment.image(util.pic2b64(res_img))

    res_text = []

    if len(new_charas) > 0:
        new_chara_names_comb = '，'.join([f'{chara.CHARA_NAME[server][c]}({chara.get_chara_rank(c)}✦)' for c in new_charas])
        res_text.append(f"获得新角色：{new_chara_names_comb}")

    if rank3_count == 0:
        if rank2_count == 1 and rank1_count == 9:
            res_text.append("惨")

    res_text.append(f"水晶{total_num_crystals}（+{num_crystals}）")
    res_text.append(f"井票{total_num_mileage_tickets}（+{num_mileage_tickets}）")
    res_text_comb = '\n'.join(res_text)

    res = f"{seg_at}\n{seg_img}\n{res_text_comb}"

    # Write user data.
    save_user_data(user_data)

    await session.send(res)


@on_command('抽一井', only_to_me=False)
async def gacha_10(session: CommandSession):
    await session.send('不抽')


@on_command('仓库', only_to_me=False)
async def gacha_storage(session: CommandSession):
    user_id = session.event['user_id']
    user_id_str = str(user_id)
    server = 'cn'

    user_data = read_user_data()
    initialize_user_server_data(user_data, user_id, server)
    user_server_data = user_data[user_id_str][server]
    all_charas = user_server_data['charas']
    total_num_crystals = user_server_data['crystals']
    total_num_mileage_tickets = user_server_data['mileage']

    # Create at message.
    seg_at = MessageSegment.at(user_id)

    res_text = []

    if len(all_charas) > 0:
        res_text.append(f"现有角色：")
        res_text.extend([f'{chara.CHARA_NAME[server][c]}({chara.get_chara_rank(c)}✦)' for c in all_charas if chara.get_chara_rank(c) == 3])
        rank2_count = sum(1 for r in all_charas if chara.get_chara_rank(r) == 2)
        rank1_count = sum(1 for r in all_charas if chara.get_chara_rank(r) == 1)
        if rank2_count > 0:
            res_text.append(f"{rank2_count}个2✦")
        if rank1_count > 0:
            res_text.append(f"{rank1_count}个1✦")
    else:
        res_text.append("你一个角色都没")

    res_text.append(f"水晶{total_num_crystals}，井票{total_num_mileage_tickets}")
    res_text_comb = '\n'.join(res_text)

    res = f"{seg_at}{res_text_comb}"
    await session.send(res)

@on_command('井', only_to_me=False)
async def gacha_tencho(session: CommandSession):
    user_id = session.event['user_id']
    user_id_str = str(user_id)
    server = 'cn'

    user_data = read_user_data()
    initialize_user_server_data(user_data, user_id, server)
    user_server_data = user_data[user_id_str][server]

    # Create at message.
    seg_at = MessageSegment.at(user_id)

    res_text = []

    if user_server_data['mileage'] < TENCHO_TICKET_COUNT:
        res_text.append(f"井票不够{TENCHO_TICKET_COUNT}！")
    else:
        arg_str = session.current_arg_text.strip()
        if arg_str in chara.CHARA_ALIAS_ID_MAP:
            chara_id = chara.CHARA_ALIAS_ID_MAP[arg_str]
            chara_rank = chara.get_chara_rank(chara_id)
            if chara_rank == 3 and chara_id in chara.CHARA_SERVER[server]:
                if chara_id in user_server_data['charas']:
                    delta_num_crystals = RANK_CRYSTAL_MAP[chara_rank]
                    res_text.append(f"重复角色，获得{delta_num_crystals}水晶")
                    user_server_data['crystals'] += delta_num_crystals
                else:
                    res_img = chara.combine_chara_thumbnails_with_rank([chara_id])
                    seg_img = MessageSegment.image(util.pic2b64(res_img))
                    res_text.append(f"{seg_img}")

                    res_text.append(f"获得{chara.CHARA_NAME[server][chara_id]}")
                    user_server_data['charas'].append(chara_id)
                user_server_data['mileage'] -= TENCHO_TICKET_COUNT
            else:
                res_text.append(f"只能兑换国服三星角色！")
        else:
            res_text.append("谁？")

    res_text_comb = '\n'.join(res_text)

    res = f"{seg_at}{res_text_comb}"

    # Write user data.
    save_user_data(user_data)

    await session.send(res)


def do_gacha_n(pool, n):
    return random.choices(
        population=list(pool.keys()),
        weights=pool.values(),
        k=n
    )

# Returns gacha result and update user data accordingly.
def do_gacha_10(user_data, user_id, server):
    user_id_str = str(user_id)
    user_server_data = user_data[user_id_str][server]
    user_charas = user_server_data['charas']

    # Adjust specific rates.
    has_fei = 'fei' in user_charas
    has_mei = 'mei' in user_charas
    has_knight_male   = 'knight_male'   in user_charas
    has_knight_female = 'knight_female' in user_charas

    if has_fei:
        fei_factor = 1.0
        mei_factor = 0.0
    else:
        if has_mei:
            fei_factor = 0.0
            mei_factor = 1.0
        else:
            is_fei = random.randint(0, 1) == 0
            fei_factor = 1.0 if     is_fei else 0.0
            mei_factor = 1.0 if not is_fei else 0.0

    if has_knight_male:
        knight_male_factor = 1.0
        knight_female_factor = 0.0
    else:
        if has_knight_female:
            knight_male_factor = 0.0
            knight_female_factor = 1.0
        else:
            is_knight_male = random.randint(0, 1) == 0
            knight_male_factor   = 1.0 if     is_knight_male else 0.0
            knight_female_factor = 1.0 if not is_knight_male else 0.0

    res = []
    pool = create_default_pool(server, fei_factor=fei_factor, mei_factor=mei_factor, knight_male_factor=knight_male_factor, knight_female_factor=knight_female_factor)
    res.extend(do_gacha_n(pool, 9))
    pool = create_default_pool(server, fei_factor=fei_factor, mei_factor=mei_factor, knight_male_factor=knight_male_factor, knight_female_factor=knight_female_factor, guarantee_2star=True)
    res.extend(do_gacha_n(pool, 1))

    # Find repetitive charas.
    num_crystals = 0
    new_charas = []
    for r in res:
        if r in user_charas:
            # Give hero crystals.
            chara_rank = chara.get_chara_rank(r)
            num_crystals += RANK_CRYSTAL_MAP[chara_rank]
        else:
            # Add chara to user data.
            new_charas.append(r)
            user_charas.append(r)

    user_server_data['crystals'] += num_crystals
    num_mileage_tickets = 10
    user_server_data['mileage'] += num_mileage_tickets

    return res, new_charas, num_crystals, num_mileage_tickets

def do_gacha_100(user_data, user_id, server):
    res = []
    new_charas = []
    num_crystals = 0
    num_mileage_tickets = 0
    for _ in range(10):
        r, nc, nc_c, nc_m = do_gacha_10(user_data, user_id, server)
        res.extend(r)
        new_charas.extend(nc)
        num_crystals += nc_c
        num_mileage_tickets += nc_m
    return res, new_charas, num_crystals, num_mileage_tickets


def initialize_user_server_data(data, user_id, server):
    user_id_str = str(user_id)
    if user_id_str not in data:
        data[user_id_str] = dict()
    if server not in data[user_id_str]:
        data[user_id_str][server] = dict()

    user_server_data = data[user_id_str][server]
    if 'charas' not in user_server_data:
        user_server_data['charas'] = []
    if 'crystals' not in user_server_data:
        user_server_data['crystals'] = 0
    if 'mileage' not in user_server_data:
        user_server_data['mileage'] = 0
    if '10_pull_count' not in user_server_data:
        user_server_data['10_pull_count'] = 0
    if 'last_10_pull_day' not in user_server_data:
        user_server_data['last_10_pull_day'] = -1
    if '100_pull_count' not in user_server_data:
        user_server_data['100_pull_count'] = 0
    if 'last_100_pull_day' not in user_server_data:
        user_server_data['last_100_pull_day'] = -1

def read_user_data():
    with open(USER_DATA_FILE, 'r') as f:
        return json.load(f)

def save_user_data(data):
    with open(USER_DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)
