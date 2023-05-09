import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.dispatcher import FSMContext

bot = Bot(token=os.getenv('TOKEN'))
dp = Dispatcher(bot, storage=MemoryStorage())
logging.basicConfig(level=logging.INFO)

# Стейты для команды /set
class Set(StatesGroup):
    service = State()
    password = State()

# Cтейт для команды /get
class Get(StatesGroup):
    service = State()

@dp.message_handler(commands=['start', 'help'])
async def cmd_start(message: types.Message):
    await message.answer('Привет!👋 Этот бот поможет тебе не потерять доступ к важным ресурсам🔒' +
                        '\nСинтаксис команд:\n/set – добавить пароль' +
                        '\n/get – получить пароль к сервису\n/del – удалить сервис')


@dp.message_handler(commands=['set'])
async def cmd_set(message: types.Message):
    await Set.service.set()
    await message.answer('Какой сервис хочешь добавить?😳')

# Ввод сервиса для /set
@dp.message_handler(state=Set.service)
async def set_service(message: types.Message, state: FSMContext):
    await Set.password.set()
    async with state.proxy() as data:
        data['service'] = message.text
    await message.answer('Вводи пароль. Не переживай, я не подглядываю😉')

# Ввод пароля для /set
@dp.message_handler(state=Set.password)
async def set_password(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        service = data['service']
    await message.answer(f'Я слил всё копам. Сервис: {service}, пароль: {message.text}\n' +
                        'Сообщение с паролем сейчас удалится. ' +
                        'Не переживай, это всё ради твоей же конфиденицальности😎')
    await state.finish()
    # Удаление сообщения
    await asyncio.sleep(2)
    await message.delete()


@dp.message_handler(commands=['get'])
async def cmd_get(message: types.Message):
    await Get.service.set()
    await message.answer('Пароль от какого сервиса показать?🥰')

@dp.message_handler(state=Get.service)
async def get_service(message: types.Message, state: FSMContext):
    service = message.text
    await state.finish()
    answer = await message.answer(f'Пароль от сервиса {service} эээ... будет')
    # Удаление сообщения
    await asyncio.sleep(5)
    await answer.delete()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
