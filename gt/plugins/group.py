import os, pathlib

from datetime import timedelta
from datetime import datetime
from pytz import timezone
from nonebot import on_command, CommandSession
from nonebot.log import logger

import config
from gt.utilities.util import TIME_ZONE, current_time
from gt.utilities import util

FILE_NAME = os.path.join(config.DATA_DIR, 'group', 'current_list.txt')

# Adds the user into the waitlist. 
@on_command('group', aliases=('组队', '合作模式', '带我一个', '想打合作了'), only_to_me=False)
async def group(session: CommandSession):
    check_dir()
    dateInFile = existing_date()
    coopTimeRange = timedelta(days = 14)

    # Checks if the coop date exists or if the current date is not valid anymore. 
    if dateInFile is None or dateInFile > current_time() or (dateInFile + coopTimeRange) < current_time()  :
        dateInFileString = '上次啥时候忘了'
        if dateInFile is not None:
            if dateInFile > current_time():
                dateInFileString = '下次时间是{}'.format(util.date_to_string_translator(dateInFile, True))
            else:
                dateInFileString = '上次已经是{}'.format(util.date_to_string_translator(dateInFile, True))
            
        currentTimeString = util.date_to_string_translator(current_time(), True)
        await session.send('合作还没开吧, 现在时间是{}，{}'.format(currentTimeString, dateInFileString))
        return
    
    event = session.event.copy()

    # Adds the sender to the waiting list if the user is not there. 
    currentIds = qqIdsInFile()
    username = event['sender']['card']
    userid = str(event['sender']['user_id'])

    if userid in currentIds:
        if len(currentIds) == 1:
            await session.send('{} 你已经在里面了，现在只有你，给老子再等等'.format(username))
            return
        await session.send('{} 你已经在里面了，现在有{}'.format(username, waitlist_user()))
        return 

    write_to_file(', '.join([username, userid]))
    
    # Sends messages if there are 4 people already. 
    with open(FILE_NAME, newline='') as f:
        rows = f.read().splitlines()
    if len(rows) > 4:
        for row in rows:
            if row.startswith('date: '):
                continue
            answerMessage = '人够了！gogogo！' + waitlist_user(True)
        # Cleans up the file if there is enough people. 
        clean_up_file(True)
    else:
        if len(qqIdsInFile()) == 1:
            answerMessage = 'okay，你是第一个哦~'
        else:
            answerMessage = '人还不够，现在{}在等'.format(waitlist_user())
    
    await session.send(answerMessage)
    return

# Remove a user from file. 
@on_command('不打了', aliases=('我不打了', '不等了', '我先开了', '下次再打', '先开了'), only_to_me=False)
async def remove_user(session: CommandSession):
    check_dir()
    currentIds = qqIdsInFile()
    event = session.event.copy()
    userid = str(event['sender']['user_id'])

    if userid in currentIds:
        remove_lines(userid)
    
    await session.send('okay，那就下次再打吧')

# Checks the current status. 
@on_command('查询合作', aliases=('查询合作模式', '查询组队', '当前合作', '几个人啊','现在几个人啊','人够不够了', '几个人'), only_to_me=False)
async def search_group(session: CommandSession):
    check_dir()

    current_team = waitlist_user()
    if current_team == '':
        await session.send('现在还没人')
        return
    
    await session.send('现在有: {}'.format(current_team))

# Checks the current co-op date. If it doesn't exists, returns error messages which requires to set date. 
@on_command('合作时间', aliases=('合作开始时间','合作模式开始时间','这次合作模式', '合作开了吗'), only_to_me=False)
async def date(session: CommandSession) -> str:
    check_dir()
    inputDate = None

    # Translates the input date into datetime type.
    arg_str = session.current_arg_text.strip()
    if arg_str != '':
        logger.debug(f'Time is "{arg_str}"')
        try: 
            inputDate = util.string_to_date_translator(arg_str)
        except ValueError:
            await session.send('你这日期有问题啊，不是mm/dd/yyyy')
            return

    dateInFile = existing_date()

    # User input doesn't contains date, assume the user wants to check the start date. 
    if inputDate is None and dateInFile is not None:
        await session.send('合作{}开始'.format(util.date_to_string_translator(dateInFile, True)))
    elif inputDate is None and dateInFile is None:
        await session.send('俺也不知道合作啥时候开始')
    elif inputDate is not None:
        clean_up_file()
        newDate = util.date_to_string_translator(inputDate)
        write_to_file(newDate)
        await session.send('新的合作时间: {}'.format(newDate[6:]))
    return

# Checks if current list exists if not create it
def check_dir():
    if not os.path.isfile(FILE_NAME):
        pathlib.Path(FILE_NAME).touch()

# Create an empty file. 
def clean_up_file(keep_existing_date = False):
    if (not keep_existing_date):
        os.remove(FILE_NAME)
        check_dir()
        return

    tempDate = existing_date()
    if tempDate is not None:
        os.remove(FILE_NAME)
        check_dir()
        newDate = util.date_to_string_translator(tempDate)
        write_to_file(newDate)

# Returns the date in the file if exists. 
def existing_date():
    with open(FILE_NAME, newline='') as f:
        rows = f.read().splitlines()

    if len(rows) > 0:
        dateRange = rows[0]
        logger.debug(f"First row in current list file: {dateRange}")
        if dateRange.startswith('date: '):
            try: 
                return util.string_to_date_translator(dateRange[6:])
            except ValueError:
                return None 

# Remove a line with certain pattern.
def remove_lines(identifier):
    with open(FILE_NAME, newline='') as f:
        rows = f.read().splitlines()
    with open(FILE_NAME, "w") as f:
        for row in rows:
            if identifier not in row:
                f.write(row + '\n')

# Returns the existing people in the file.
def waitlist_user(pingUser = False):
    with open(FILE_NAME, newline='') as f:
        rows = f.read().splitlines()

    if not pingUser:
        return ', '.join([rows[i].split(',')[0] for i in range(1, len(rows))])

    return ', '.join([at_user(rows[i].split(',')[1]) for i in range(1, len(rows))])

# Returns the string required to @ someone. 
def at_user(qqId):
    return '[CQ:at,qq={}]'.format(qqId.strip())

# Returns the ids existing in the current file. 
def qqIdsInFile():
    with open(FILE_NAME, newline='') as f:
        rows = f.read().splitlines()
    return [rows[i].split(',')[1].strip() for i in range(1, len(rows))]

# Write contents in a text file.
def write_to_file(content):
    with open(FILE_NAME, 'a', newline='') as f:
        f.write(content + '\n')
