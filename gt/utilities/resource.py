import os
from os import path

import requests
from bs4 import BeautifulSoup
from PIL import Image

import config

PNG_FILE_DIR = path.join(config.DATA_DIR, 'cache', 'chara-png')
IMAGE_SEND_QUEUE_CACHE_DIR = path.join(config.CQ_DATA_DIR, 'data', 'cache', 'image-send-queue')
IMAGE_SEND_QUEUE_CACHE_MNT_DIR = path.join(config.CQ_MNT_DATA_DIR, 'data', 'cache', 'image-send-queue')
image_send_queue_id = 0

def find_png_in_biliwiki(filename):
    url_wiki = "https://wiki.biligame.com/gt/文件:{}.png".format(filename)
    r_wiki = requests.get(url_wiki)

    if r_wiki.status_code != 200:
        raise Exception(f"Failed to get {filename}.png download link.")

    bs_wiki = BeautifulSoup(r_wiki.text, "html.parser")
    url_png = bs_wiki.body.find('div', attrs={'class': 'fullImageLink'}).find('a')['href']
    r_png = requests.get(url_png, stream=True)

    if r_png.status_code != 200:
        raise Exception(f"Failed to download {filename}.png file.")

    return r_png.content

def get_chara_png_file(filename):
    fullname = path.join(PNG_FILE_DIR, filename + '.png')
    if not path.isfile(fullname):
        os.makedirs(PNG_FILE_DIR, exist_ok=True)
        with open(fullname, 'wb') as f:
            f.write(find_png_in_biliwiki(filename))

    return fullname

def get_rank_png_file(rank:int):
    if rank < 1 or rank > 3:
        raise Exception(f"Rank {rank} is not in range [1, 3].")

    filename = f'Rank{rank}_{rank}'
    fullname = path.join(PNG_FILE_DIR, filename + '.png')
    if not path.isfile(fullname):
        os.makedirs(PNG_FILE_DIR, exist_ok=True)
        with open(fullname, 'wb') as f:
            f.write(find_png_in_biliwiki(filename))
    return fullname

def push_image_send_queue(im):
    global image_send_queue_id
    image_name = f'{image_send_queue_id}.png'
    os.makedirs(IMAGE_SEND_QUEUE_CACHE_DIR, exist_ok=True)
    im.save(path.join(IMAGE_SEND_QUEUE_CACHE_DIR, image_name))
    image_send_queue_id += 1
    return image_name

if __name__ == "__main__":
    png_content = find_png_in_biliwiki("未来公主单个模型")
    with open("未来公主单个模型.png", "wb") as f:
        f.write(png_content)
