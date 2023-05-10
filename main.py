import asyncio
import os
import logging
from sqlalchemy import Column, Integer, ForeignKey, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.dispatcher import FSMContext

engine = create_engine('postgresql://postgres:example@localhost:8080/postgres')
Base = declarative_base()
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
session = DBSession()

# Модели двух таблиц БД
class Users(Base):
    __tablename__ = 'users'
    user_id = Column(Integer, primary_key=True)

class Passwords(Base):
    __tablename__ = 'passwords'
    id = Column(Integer, primary_key=True)
    service = Column(String(100))
    password = Column(String(100))
    user_id = Column(ForeignKey('users.user_id'))

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

# Cтейт для команды /get
class Del(StatesGroup):
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
    service = message.text
    user_id = message.from_user.id

    # Проверка существования записи о сервисе в бд
    if not session.query(Passwords).filter_by(user_id=user_id, service=service).first():
        await Set.password.set()
        async with state.proxy() as data:
            data['service'] = service
        await message.answer('Вводи пароль. Не переживай, я не подглядываю😉')
    else:
        await state.finish()
        await message.answer('Ты уже добавлял этот сервис🥺' +
                            '\nВведи /set снова')


# Ввод пароля для /set
@dp.message_handler(state=Set.password)
async def set_password(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        service = data['service']

    # Добавление юзера в бд
    user_id = message.from_user.id
    if not session.query(Users).filter_by(user_id=user_id).first():
        user = Users(user_id=user_id)
        session.add(user)
        session.commit()

    # Добавление записи о сервисе
    password = Passwords(service=service, password=message.text, user_id=user_id)
    session.add(password)
    session.commit()

    await message.answer('Сервис успешно добавлен!\n' +
                        'Сообщение с паролем сейчас удалится. ' +
                        'Не переживай, это ради твоей же конфиденциальности😎')
    await state.finish()
    # Удаление сообщения
    await asyncio.sleep(2)
    await message.delete()


@dp.message_handler(commands=['get'])
async def cmd_get(message: types.Message):
    await Get.service.set()
    await message.answer('Пароль от какого сервиса показать?🥰')

# Ввод сервиса для /get
@dp.message_handler(state=Get.service)
async def get_service(message: types.Message, state: FSMContext):
    service = message.text
    user_id = message.from_user.id

    # Получить запись о пароле
    password = session.query(Passwords).filter_by(service=service, user_id=user_id).first()
    if password:
        answer = await message.answer(f'Пароль от сервиса {service}: {password.password}')
        # Удаление сообщения
        await asyncio.sleep(5)
        await answer.delete()
    else:
        await message.answer('Сервис не был найден, сперва добавь его через /set 😊')
    await state.finish()


@dp.message_handler(commands=['del'])
async def cmd_del(message: types.Message):
    await Del.service.set()
    await message.answer('Какой сервис удаляем?😭')

# Ввод сервиса для /del
@dp.message_handler(state=Del.service)
async def del_service(message: types.Message, state: FSMContext):
    service = message.text
    await state.finish()
    await message.answer(f'Сервис {service} удалён🫥')


if __name__ == '__main__':
    Base.metadata.create_all(engine)
    executor.start_polling(dp)
