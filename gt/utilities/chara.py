import json
from os import path

import pandas
from PIL import Image

import config
import gt.utilities.resource as resource

CHARA_INFO_FILE = path.join(config.INTERNAL_DATA_DIR, 'list', 'charainfo.csv')
CHARA_INFO = pandas.read_csv(CHARA_INFO_FILE, encoding='utf-8')

# CHARA_NAME should be a dict of language -> (dict of chara_id -> chara_name), read from charaname.json
CHARA_NAME_FILE = path.join(config.INTERNAL_DATA_DIR, 'list', 'charaname.json')
with open(CHARA_NAME_FILE, 'r', encoding='utf-8') as f:
    CHARA_NAME = json.load(f)

CHARA_SERVER_FILE = path.join(config.INTERNAL_DATA_DIR, 'list', 'charaserver.json')
with open(CHARA_SERVER_FILE, 'r', encoding='utf-8') as f:
    CHARA_SERVER = json.load(f)

CHARA_ALIAS_FILE = path.join(config.INTERNAL_DATA_DIR, 'list', 'charaalias.json')
with open(CHARA_ALIAS_FILE, 'r', encoding='utf-8') as f:
    CHARA_ALIAS = json.load(f)

CHARA_ALIAS_ID_MAP = {}
for chara_id, alias_list in CHARA_ALIAS.items():
    for alias in alias_list:
        CHARA_ALIAS_ID_MAP[alias] = chara_id

def get_chara_rank(chara_id):
    return CHARA_INFO[CHARA_INFO.name == chara_id].initstar.values[0]

def get_chara_thumbnail(chara_id):
    chara_name = CHARA_NAME['cn-biliwiki'][chara_id]
    png_name = chara_name + "单个模型"
    return Image.open(resource.get_chara_png_file(png_name))

def get_rank_thumbnail(rank:int):
    return Image.open(resource.get_rank_png_file(rank))

def combine_chara_thumbnails_with_rank(chara_ids, nres_line=5):
    ims = [get_chara_thumbnail(chara_id) for chara_id in chara_ids]
    ims_rank = [get_rank_thumbnail(rank) for rank in range(1, 4)]

    max_width = max(im.width for im in ims)
    rank_scale = max_width / ims_rank[0].width
    ims_rank = [im.resize((int(im.width * rank_scale), int(im.height * rank_scale))) for im in ims_rank]
    rank_height = ims_rank[0].height

    tot_height = 0
    for i in range(0, len(ims), nres_line):
        im_range = ims[i:i+nres_line]
        max_height = max(im.height for im in im_range)
        tot_height += max_height + rank_height

    res = Image.new('RGBA', (max_width * nres_line, tot_height), (225, 0, 0, 0))
    y = 0
    for i in range(0, len(ims), nres_line):
        im_range = ims[i:i+nres_line]
        max_height = max(im.height for im in im_range)
        for j in range(len(im_range)):
            chara_rank = CHARA_INFO[CHARA_INFO.name == chara_ids[i+j]].initstar.values[0]
            im = im_range[j]
            im_rank = ims_rank[chara_rank-1]
            res.paste(im, (j * max_width, y))
            res.paste(im_rank, (j * max_width, y + max_height))
        y += max_height + rank_height

    return res
