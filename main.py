import aiogram
import os

token = os.getenv('TOKEN')
bot = Bot(token=token)
dp = Dispatcher(bot, storage=MemoryStorage())