import asyncio
import base64
from collections import defaultdict
from datetime import datetime
from io import BytesIO
from enum import Enum
from PIL import Image
import pytz

TIME_ZONE = pytz.timezone('Asia/Shanghai')

# Timer copied from https://stackoverflow.com/questions/45419723/python-timer-with-asyncio-coroutine
class Timer:
    def __init__(self, timeout, callback, *cb_args):
        self._timeout = timeout
        self._callback = callback
        self._task = asyncio.ensure_future(self._job(*cb_args))

    async def _job(self, *cb_args):
        await asyncio.sleep(self._timeout)
        await self._callback(*cb_args)

    def cancel(self):
        self._task.cancel()

# Category for food: Meat, Fish, Vegetable, Drink, Snack, Bell pepper.
class Category(Enum):
    MEAT = 1
    FISH = 2
    VEGETABLE = 3
    DRINK = 4
    SNACK = 5
    BELL_PEPPER = 6

# Available tiem for food: Breakfast, Lunch, Dinner. 
class FoodTime(Enum):
    BREAKFAST = 1
    LUNCH = 2
    DINNER = 3

# Auxiliary functions for date times.
#---------------------------------------

# Current time
def current_time():
    return datetime.now(TIME_ZONE)

# Translates a string into date. 
def string_to_date_translator(stringInput) -> datetime:
    return datetime.strptime(stringInput, '%m/%d/%Y').replace(tzinfo=TIME_ZONE)

# Translates a date into string with title. 
def date_to_string_translator(dateInput, noHeader = False) -> str:
    newString = dateInput.strftime('%m/%d/%Y')
    if (noHeader):
        return newString
    return 'date: {}'.format(newString)



# Copied from HoshinoBot.
def pic2b64(pic:Image) -> str:
    buf = BytesIO()
    pic.save(buf, format='PNG')
    base64_str = base64.b64encode(buf.getvalue()).decode()
    return 'base64://' + base64_str
