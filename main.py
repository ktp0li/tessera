import asyncio
import os
import logging
from sqlalchemy import Column, Integer, ForeignKey, String, create_engine, LargeBinary
from sqlalchemy.orm import declarative_base, sessionmaker
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.dispatcher import FSMContext
from Crypto.Cipher import AES

dbuser, dbpass, dbhost = os.getenv("DB_USER"), os.getenv("DB_PASS"), os.getenv("DB_HOST")
dbport, dbname = os.getenv("DB_PORT"), os.getenv("DB_NAME")
engine = create_engine(f'postgresql://{dbname}:{dbpass}@{dbhost}:{dbport}/{dbname}')
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
    service = Column(String(63))
    login = Column(String(63))
    #password = Column(String(63))
    ciphertext = Column(LargeBinary(63))
    tag = Column(LargeBinary(16))
    nonce = Column(LargeBinary(16))
    user_id = Column(ForeignKey('users.user_id'))

bot = Bot(token=os.getenv('TOKEN'))
dp = Dispatcher(bot, storage=MemoryStorage())
logging.basicConfig(level=logging.INFO)

# Стейты для команды /set
class Set(StatesGroup):
    service = State()
    login = State()
    password = State()

# Cтейты для команды /get
class Get(StatesGroup):
    service = State()
    login = State()

# Cтейты для команды /get
class Del(StatesGroup):
    service = State()
    login = State()


# Добавление шифра
key = os.getenv('KEY').encode()

# Шифрование паролей
async def encode(data):
    data = data.encode()
    cipher = AES.new(key, AES.MODE_EAX)
    ciphertext, tag = cipher.encrypt_and_digest(data)
    nonce = cipher.nonce
    return {'ciphertext': ciphertext, 'tag': tag, 'nonce': nonce}

# Дешифрование паролей
async def decode(ciphertext, tag, nonce):
    cipher = AES.new(key, AES.MODE_EAX, nonce)
    return cipher.decrypt_and_verify(ciphertext, tag)


@dp.message_handler(commands=['start', 'help'])
async def cmd_start(message: types.Message):
    await message.answer('Привет! 👋 Этот бот поможет тебе не потерять доступ к важным ресурсам 🔒' +
                        '\nСинтаксис команд:\n/set – добавить пароль' +
                        '\n/get – получить пароль к сервису\n/del – удалить сервис' +
                        '\n/list – список добавленных сервисов')


@dp.message_handler(commands=['set'])
async def cmd_set(message: types.Message):
    await Set.service.set()
    await message.answer('Какой сервис хочешь добавить? 😳')

# Ввод сервиса для /set
@dp.message_handler(state=Set.service)
async def set_service(message: types.Message, state: FSMContext):
    service = message.text
    if len(service) <= 63:
        async with state.proxy() as data:
            data['service'] = service

        await Set.login.set()
        await message.answer('Какой логин для сервиса добавишь? 🤔')
    else:
        await state.finish()
        await message.answer('Название сервиса слишком длинное 🥺' +
                            '\nВведи /set снова')

# Ввод логина для /set
@dp.message_handler(state=Set.login)
async def set_login(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    log = message.text

    if len(log) <= 63:
        async with state.proxy() as data:
            data['login'] = log
            service = data['service']

        # Проверка существования записи о логине в бд
        if not session.query(Passwords).filter_by(user_id=user_id, service=service, login=log).first():
            await Set.password.set()
            await message.answer('Вводи пароль. Не переживай, я не подглядываю 😉')
        else:
            state.finish()
            await message.answer('Ты уже добавлял этот логин к сервису 🥺' +
                                 '\nВведи /set снова')
    else:
        await state.finish()
        await message.answer('Логин слишком длинный 🥺' +
                             '\nВведи /set снова')

# Ввод пароля для /set
@dp.message_handler(state=Set.password)
async def set_password(message: types.Message, state: FSMContext):
    passw = message.text

    if len(passw) <= 63:
        async with state.proxy() as data:
            service = data['service']
            log = data['login']

        # Добавление юзера в бд
        user_id = message.from_user.id
        if not session.query(Users).filter_by(user_id=user_id).first():
            user = Users(user_id=user_id)
            session.add(user)
            session.commit()

        # Добавление записи о сервисе
        encoded = await encode(passw)
        password = Passwords(service=service, login=log, ciphertext=encoded['ciphertext'],
                             tag=encoded['tag'], nonce=encoded['nonce'], user_id=user_id)
        session.add(password)
        session.commit()

        await message.answer('Сервис успешно добавлен!\n' +
                            'Сообщение с паролем сейчас удалится. ' +
                            'Не переживай, это ради твоей же конфиденциальности 😎')
        await state.finish()
        # Удаление сообщения
        await asyncio.sleep(2)
        await message.delete()
    else:
        await state.finish()
        await message.answer('Пароль слишком длинный 🥺' +
                             '\nВведи /set снова')



@dp.message_handler(commands=['get'])
async def cmd_get(message: types.Message):
    await Get.service.set()
    await message.answer('Пароль от какого сервиса показать? 🥰')

# Ввод сервиса для /get
@dp.message_handler(state=Get.service)
async def get_service(message: types.Message, state: FSMContext):
    service = message.text
    async with state.proxy() as data:
        data['service'] = service
    user_id = message.from_user.id

    # Получить запись о пароле
    entry = session.query(Passwords).filter_by(service=service, user_id=user_id).first()
    if entry:
        await message.answer('Какой логин использовал при регистрации? 😳')
        await Get.login.set()
    else:
        await message.answer('Сервис не был найден, сперва добавь его через /set 😊')
        await state.finish()

# Ввод логина для /get
@dp.message_handler(state=Get.login)
async def get_login(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    log = message.text
    async with state.proxy() as data:
        service = data['service']

    # Получить запись о пароле
    entry = session.query(Passwords).filter_by(service=service, login=log, user_id=user_id).first()
    if entry:
        password = await decode(entry.ciphertext, entry.tag, entry.nonce)
        answer = await message.answer(f'Пароль от сервиса: `{password.decode("utf-8")}`', parse_mode="MarkdownV2")
        await state.finish()
        # Удаление сообщения
        await asyncio.sleep(5)
        await answer.delete()
    else:
        await message.answer('Логин для сервиса не был найден, сперва добавь его через /set 😊')
        await state.finish()



@dp.message_handler(commands=['del'])
async def cmd_del(message: types.Message):
    await Del.service.set()
    await message.answer('Пароль от какого сервиса удаляем? 😭')

# Ввод сервиса для /del
@dp.message_handler(state=Del.service)
async def del_service(message: types.Message, state: FSMContext):
    service = message.text
    user_id = message.from_user.id
    async with state.proxy() as data:
        data['service'] = service

    # Получить запись о пароле
    entry = session.query(Passwords).filter_by(service=service, user_id=user_id).first()
    if entry:
        await Del.login.set()
        await message.answer('А логин какой? 🤔')
    else:
        await state.finish()
        await message.answer('Сервис не был найден, сперва добавь его через /set 😊')

# Ввод логина для /del
@dp.message_handler(state=Del.login)
async def del_login(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        service = data['service']
    user_id = message.from_user.id
    log = message.text

    entry = session.query(Passwords).filter_by(service=service, login=log,user_id=user_id).first()
    if entry:
        session.delete(entry)
        session.commit()
        await message.answer('Пароль удалён🫥')
    else:
        await message.answer('Логин для сервиса не был найден, сперва добавь его через /set 😊')
    await state.finish()


@dp.message_handler(commands=['list'])
async def cmd_list(message: types.Message):
    user_id = message.from_user.id
    services = [i.service for i in session.query(Passwords).filter_by(user_id=user_id).all()]
    entries = {}
    for i in services:
        query = session.query(Passwords).filter_by(user_id=user_id, service=i).all()
        entries[i] = [i.login for i in query]
    entr = [f'🫃 {j}:' + '\n    👁️ ' + '\n    👁️ '.join(k) for j, k in entries.items()]
    if entr:
        await message.answer('Добавленные сервисы:\n' + '\n'.join(entr))
    else:
        await message.answer('Ты пока не добавил ни одного пароля 😭')


if  __name__ == '__main__':
    Base.metadata.create_all(engine)
    executor.start_polling(dp)
