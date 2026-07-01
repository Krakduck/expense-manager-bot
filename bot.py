import asyncio
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command,CallbackData
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import random
import html
import os
from database_iogram import UserDatabase

bot_token = os.getenv('BOT_TOKEN')
admin_id = int(os.getenv('ADMIN_ID'))

async def main():
    bot = Bot(token=bot_token)
    dp=Dispatcher()
    db=UserDatabase()

    # 1. Инициализируем ЕДИНОЕ соединение с БД перед созданием таблиц
    await db.connect()

    # 2. Подключаем обработчики
    dp.include_router(router)

    # 3. А вот так мы запускаем создание таблицы при старте!
    print("Создаем таблицы в базе данных...")
    await db.create_table()

    # Инициализируем планировщик
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

    scheduler.start()

    await dp.start_polling(bot, db=db, scheduler=scheduler)

    # 4. Запускаем бота (polling)
    print("Бот успешно запущен!")
    await dp.start_polling(bot,db=db)



async def scheduled_task(bot: Bot, chat_id: int, db: UserDatabase, event_id: int):
    if await db.event_continue_streak(event_id):
        await bot.send_message(chat_id=chat_id, text="⏰ Серия продлена!")

# Создаем роутер (маршрутизатор) для наших обработчиков
router = Router()

class UpdateName(StatesGroup): # класс создается как контейнер. он нужен для логического объединения функций, относящихся к регистрации
    waiting_for_data = State()# это и есть создание конкретного «статуса» (состояния). Когда пользователь пишет боту, aiogram смотрит на этого пользователя и спрашивает у своей памяти:
                          # «У Романа сейчас включен маркер Registration.waiting_for_data?». Если да, то сообщение отправляется в функцию регистрации, а не в игру или главное меню.
                         #Грубо говоря, aiogram внутри себя превращает это в обычную строку, например: "Registration:waiting_for_data".Там лежит объект-указатель, имя которого строго привязано к твоему классу.

#waiting_for_event = State()      # Шаг 1: Ждем текст/название
#waiting_for_description = State() # Шаг 2: Ждем описание (если нужно)
#waiting_for_date = State()        # Шаг 3: Ждем дату (если нужно)

class Delete(StatesGroup):
    waiting_for_delete = State()

class Spent(StatesGroup):
    waiting_for_spent = State()

class Answer (StatesGroup):
    waiting_for_answer = State()

class Citation (StatesGroup):
    waiting_for_citation = State()

class CreateEvent (StatesGroup):
    waiting_for_event = State()

class DeleteEventCallback(CallbackData, prefix="del_evt"):
    event_id: int  # Передаем ID события как число

class ContinueEventCallback(CallbackData, prefix="cont_evt"):
    event_id: int  # Передаем ID события как число

def format_user_profile(user_data: dict) -> str:
    return (
        f"👤 **Профиль пользователя**\n\n"
        f"ID: `{user_data['telegram_id']}`\n"
        f"Имя: {user_data['username']}\n"
        f"Статус: {'Администратор' if user_data['is_admin'] else 'Пользователь'}"
    )

async def debts(message: Message,db: UserDatabase):
    users= await db.get_all_users_id()
    balances={}
    mes=''
    if users:
        for user in users:
            balances[user] = 0
        transactions = await db.get_transaction(message.chat.id)
        for trans in transactions:
            if trans['debtor_id'] is None:
                balances[trans['buyer_id']] += trans['amount']
                for user in users:
                     balances[user] -= trans['amount']/len(users)
            else:
                balances[trans['buyer_id']] += trans['amount']
                balances[trans['debtor_id']] -= trans['amount']
        named_balances = {}
        for user_id, balance in balances.items():
            user_data = await db.get_user(user_id)
            if user_data:
                # Берём имя пользователя из БД
                name = user_data['username']
                named_balances[name] = balance

        debtors = [[u, abs(b)] for u, b in balances.items() if b < 0]
        creditors = [[u, b] for u, b in balances.items() if b > 0]

        # Пока у нас есть должники и кредиторы
        while debtors and creditors:
            # Берем первых из списка
            debtor = debtors[0]
            creditor = creditors[0]

            # Находим минимальную сумму для перевода между ними
            amount_to_pay = min(debtor[1], creditor[1])

            # Записываем, кто кому переводит
            mes += f"👤 ID {debtor[0]} ➡️ должен перевести {amount_to_pay:.2f} руб. ➡️ ID {creditor[0]}\n"

            # Вычитаем переведенную сумму из их текущего долга/кредита
            debtor[1] -= amount_to_pay
            creditor[1] -= amount_to_pay

            # Если долг или кредит закрыт — удаляем участника из списка
            if debtor[1] == 0:
                debtors.pop(0)
            if creditor[1] == 0:
                creditors.pop(0)
        if not mes.strip():
            mes = "✅ Никто никому ничего не должен! Все в расчете."
        await message.answer(mes)

#---------------------------------------------COMMANDS------------------------------------------------------------------

@router.message(Command('start'))
async def start_reg(message: Message, db: UserDatabase):
    if await db.get_user(message.from_user.id) is None:
        user_id = message.from_user.id
        name = f"@{message.from_user.username}" if message.from_user.username else f"Пользователь_{message.from_user.id}"
        is_admin = False
        if user_id == 1422346075:
            is_admin = True
        await db.add_user(user_id,is_admin,name,None)
        await message.answer('Пожалуйста, измените имя в настройках профиля, чтобы участники беседы понимали кто Вы')
    await message.answer('💰 Бот-Счетовод: Как это работает?\n'
                         'Я помогаю компаниям делить совместные расходы и автоматически рассчитываю, кто кому и сколько должен перевести.\n'
                         '📊 Основные команды:\n'
                         '🔹 /del_profile — Удалить учетной записи.\n'
                         '🔹 /spent — Добавить новую трату. Бот спросит сумму, описание и на кого записать расход (на конкретного человека или на всех).\n'
                         '🔹 /debts — Показать итоговый баланс и оптимальную цепочку переводов для закрытия долгов.\n'
                         '🔹 /clear_debt — Сбросить всю историю трат (для админов).\n'
                         '🔹 /random — Выбрать случайного пользователя.\n'
                         '🔹 /all — Упомянуть всех участников чата для быстрого сбора.\n'
                         '⚙️ Попробуй также команду /profile, чтобы настроить свой профиль!')

@router.message(Command("profile"))
async def call_menu(message: Message):
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="👤 Мой профиль",
        callback_data="user_info"
    ))
    builder.add(InlineKeyboardButton(
        text="📝 Задать ответ на пинг",
        callback_data="auto_answer"
    ))
    builder.adjust(1)
    await message.answer(
        "Выбери, что тебя интересует 👇",
        reply_markup=builder.as_markup()
    )

@router.message(Command("del_profile"))
async def del_profile(message: Message, state: FSMContext):
    if message.from_user.id == admin_id:
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="Снести всю базу", callback_data="delete_all"))
        builder.add(InlineKeyboardButton(text="Удалить себя", callback_data="delete_admin"))
        builder.adjust(1)
        await message.answer('Что именно удалить?', reply_markup=builder.as_markup())
    else:
        await message.answer("Вы уверены, что хотите удалить аккаунт? Напишите да/нет")
        await state.set_state(Delete.waiting_for_delete)

@router.message(Command("spent"))
async def spent(message: Message, state: FSMContext):
    await message.answer('Напиши сообщение в формате "сумма описание имя"\n'
                         'К примеру, 1000 пицца все,\n'
                         '25 рублей вода @123.\n'
                         'Учти, что в поле "имя" нужно писать либо юзернейм человека, либо "все"')
    await state.set_state(Spent.waiting_for_spent)

@router.message(Command("debts"))
async def debt_await(message: Message, db: UserDatabase):
    await debts(message, db)

@router.message(Command("clear_debt"))
async def clear_debt(message: Message, db: UserDatabase):
    if message.from_user.id == admin_id:
        if await db.clear_debt(message.chat.id):
            await message.answer('Все долги списаны!')
        else:
            await message.answer('Что-то пошло не так')
    else:
        await message.answer('Долги списать может только админ')

@router.message(Command("random"))
async def random_user(message: Message, db: UserDatabase):
    users = await db.get_all_users_id()
    if users:
        random_id = random.choice(users)
        user_data=await db.get_user(random_id)
        # html.escape превратит небезопасные <, >, & в безопасные сущности
        safe_name = html.escape(user_data['username'])
        mes = f'<a href="tg://user?id={random_id}">{safe_name}</a>'
        await message.answer(mes, parse_mode="HTML")

@router.message(Command("all"))
async def all_user(message: Message, db: UserDatabase):
    mes=''
    users = await db.get_all_users_id()
    for user_id in users:
        # Получаем данные пользователя по его ID
        user_data = await db.get_user(user_id)
        if user_data:
            safe_name = html.escape(user_data['username'])
            mes += f'<a href="tg://user?id={user_id}">{safe_name}</a> '
    await message.answer(mes, parse_mode="HTML")

@router.message(Command("help"))
async def help_user(message: Message):
    await message.answer('💰 Бот-Счетовод: Как это работает?\n'
                         'Я помогаю компаниям делить совместные расходы и автоматически рассчитываю, кто кому и сколько должен перевести.\n'
                         '📊 Основные команды:\n'
                         '🔹 /del_profile — Удалить учетной записи.\n'
                         '🔹 /spent — Добавить новую трату. Бот спросит сумму, описание и на кого записать расход (на конкретного человека или на всех).\n'
                         '🔹 /debts — Показать итоговый баланс и оптимальную цепочку переводов для закрытия долгов.\n'
                         '🔹 /clear_debt — Сбросить всю историю трат (для админов).\n'
                         '🔹 /random — Выбрать случайного пользователя.\n'
                         '🔹 /all — Упомянуть всех участников чата для быстрого сбора.\n'
                         '⚙️ Попробуй также команду /profile, чтобы настроить свой профиль!')

@router.message(Command("save"))
async def save_reply_message(message: Message, db: UserDatabase):
    if not message.reply_to_message:
        await message.answer("❌ Эту команду нужно вызывать в ответ на сообщение, которое вы хотите сохранить!")
        return

    target_message = message.reply_to_message
    text=target_message.text
    tg_id = target_message.from_user.id
    if await db.save_citation(tg_id, text):
        await message.answer("Сообщение успешно сохранено!")
    else:
        await message.answer("Произошла ошибка сохранения!")

@router.message(Command("citations"))
async def citations(message: Message):
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="Все цитаты",
        callback_data="all_citations"
    ))
    builder.add(InlineKeyboardButton(
        text="Цитаты конкретного человека",
        callback_data="someone_citations"
    ))
    builder.adjust(1)
    await message.answer(
        "Выбери, что тебя интересует 👇",
        reply_markup=builder.as_markup()
    )

@router.message(Command("event"))
async def counter(message: Message):
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="Создать событие",
        callback_data="create_event"
    ))
    builder.add(InlineKeyboardButton(
        text="Удалить событие",
        callback_data="del_event"
    ))
    builder.add(InlineKeyboardButton(
        text="Продлить вручную",
        callback_data="continue_event"
    ))
    builder.adjust(1)
    await message.answer(
        "Выбери, что тебя интересует 👇",
        reply_markup=builder.as_markup()
    )

#-------------------------------------STATE-----------------------------------------------------------------------------

@router.message(Delete.waiting_for_delete)
async def delete_user(message: Message, state: FSMContext, db: UserDatabase):
    if message.text.strip().lower() == "да":
        await db.delete_user(message.from_user.id)
        await state.clear()
    elif message.text.strip().lower() == "нет":
        await message.answer("Операция прекращена")
        await state.clear()
    else:
        await message.answer("Напишите да/нет")

@router.message(Spent.waiting_for_spent)
async def process_spent(message: Message, state: FSMContext, db: UserDatabase):
    data = message.text.strip().split()
    if len(data) == 3:
        amount_str,description,target=data
        buyer_id= message.from_user.id
        # 1. Проверяем сумму
        try:
            amount = float(amount_str)
        except ValueError:
            await message.answer("❌ Сумма должна быть числом!")
            return
        # 2. Определяем должника
        if target.lower() == "все":
            debtor_id = None
        else:
            # Ищем ID пользователя среди упоминаний в сообщении
            #debtor_id = None
            #if message.entities:
            #    for entity in message.entities:
            #        if entity.type == "text_mention":  # Если у пользователя нет @username, но его имя кликабельно
            #            debtor_id = entity.user.id
            #        elif entity.type == "mention":  # Если это обычный @username
            #            # Для обычного mention нам придется спросить нашу БД,
            #            # успел ли этот @username хоть раз отметиться в боте
            #            debtor_id = await db.get_user_by_username(target)
            debtor_id=await db.get_user_by_username(target.lower())

        # 3. Записываем в базу
        if target.lower() != "все" and debtor_id is None:
             await message.answer("❌ Я не знаю этого пользователя. Пусть он сначала напишет мне в ЛС /start")
             return

        await db.add_transaction(message.chat.id, buyer_id, amount, description, debtor_id)
        await message.answer(f"✅ Трата успешно записана!")
        await state.clear()
    else:
        await message.answer("❌ Неверный формат. Нужно: `Сумма Описание Кому`")

@router.message(Answer.waiting_for_answer)
async def process_answer(message: Message, db: UserDatabase, state: FSMContext):
    text =message.text.strip().lower()
    if await db.update_user_param(message.from_user.id,'auto_answer',text):
        await message.answer('Фраза успешно изменена!')
    await state.clear()

@router.message(Citation.waiting_for_citation)
async def process_someone_citations(message: Message, db: UserDatabase, state: FSMContext):
    if len(message.text.strip().split()) == 1:
        tg_id= await db.get_user_by_username(message.text)
        data = await db.get_citation(tg_id)
        mes=f'Вот все цитаты {message.text}:\n\n'
        for cit in data:
            mes+=f'"{cit}"\n'
        await message.answer(mes)
        await state.clear()
    else:
        await message.answer("Отправь ТОЛЬКО юз человека ")

@router.message(CreateEvent.waiting_for_event)
async def process_create_event(message: Message, db: UserDatabase, state: FSMContext, scheduler: AsyncIOScheduler):
    current_chat_id = message.chat.id
    # Добавляем задачу (Job)
    data = await state.get_data()
    counter_type = data.get("counter_type")
    text = message.text.strip()
    event_id = await db.add_event(0, text, counter_type)
    if event_id is not None:
        scheduler.add_job(
            scheduled_task,
            trigger='cron',
            hour=0,
            minute=0,
            kwargs={
                'bot': message.bot,  # Передаем живой объект бота из message
                'chat_id': current_chat_id,
                'db': db,  # Передаем нашу базу
                'event_id': event_id  # Передаем ID события
            },
            id=f"job_{current_chat_id}_{event_id}"
            # Делаем ID уникальным, чтобы задачи разных чатов не затирали друг друга
        )
        await message.answer('Событие добавлено!')
    else:
        await message.answer('Ошибка добавления!')

    await state.clear()

#-------------------------------------CALLBACK--------------------------------------------------------------------------

@router.callback_query(F.data == "auto_answer")
async def set_auto_answer(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer('Напишите в чат фразу, которой бот будет отвечать на то, когда вас упоминают')
    await state.set_state(Answer.waiting_for_answer)

@router.callback_query(F.data == "delete_admin")
async def delete_admin(callback: CallbackQuery, db: UserDatabase):
    await callback.answer()
    if await db.delete_user(callback.from_user.id):
        await callback.message.answer("Ваш аккаунт удален")
    else:
        await callback.message.answer("Что-то пошло не так")

@router.callback_query(F.data == "delete_all")
async def delete_all(callback: CallbackQuery, db: UserDatabase):
    await callback.answer()
    if await db.delete_all_users():
        await callback.message.answer("База успешна удалена")
    else:
        await callback.message.answer("Что-то пошло не так")

@router.callback_query(F.data == "user_info")
async def process_user_info(callback: CallbackQuery, db: UserDatabase):
    # Гасим анимацию загрузки на кнопке
    await callback.answer()

    user = await db.get_user(callback.from_user.id)
    if user:
        text = format_user_profile(user)  # Используем общую функцию
        await callback.message.answer(text)
    else:
        await callback.message.answer("❌ Вы не зарегистрированы. Напишите /start")

@router.callback_query(F.data == "all_citations")
async def process_all_citations(callback: CallbackQuery, db: UserDatabase):
    await callback.answer()
    data = await db.get_all_citation()
    mes=''
    for cit in data:
        tg_id, citation = cit
        user_info=await db.get_user(tg_id)
        username = user_info['username']
        mes+=f'{username} сказал/а:"{citation}"\n'
    if mes:
        await callback.message.answer(mes)

@router.callback_query(F.data == "someone_citations")
async def someone_citations(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer('Напиши юз человека, чьи цитаты хочешь посмотреть ')
    await state.set_state(Citation.waiting_for_citation)

@router.callback_query(F.data == "create_event")
async def create_event(callback: CallbackQuery):
    await callback.answer()
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="Автоматическое продление серии",
        callback_data="auto_counter"
    ))
    builder.add(InlineKeyboardButton(
        text="Ручное продление серии",
        callback_data="manual_counter"
    ))
    builder.adjust(1)
    await callback.edit_message_text(
        "Выберите режим события",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data == "del_event")
async def delete_event(callback: CallbackQuery, db: UserDatabase):
    await callback.answer()
    builder = InlineKeyboardBuilder()
    data = await db.get_all_event()
    if data:
        for event in data:
            text = event[2]
            ev_id=event[0]
            builder.add(InlineKeyboardButton(
                text=text,
                callback_data=DeleteEventCallback(event_id=ev_id).pack()
            ))
        builder.adjust(1)
        await callback.message.answer("Выберите событие для удаления:", reply_markup=builder.as_markup())
    else:
        await callback.message.answer("У вас пока нет созданных событий.")

@router.callback_query(F.data == "continue_event")
async def continue_event(callback: CallbackQuery,  db: UserDatabase):
    await callback.answer()
    builder = InlineKeyboardBuilder()
    data = await db.get_all_event()
    if data:
        for event in data:
            text = event[2]
            ev_id = event[0]
            builder.add(InlineKeyboardButton(
                text=text,
                callback_data=ContinueEventCallback(event_id=ev_id).pack()
            ))
        builder.adjust(1)
        await callback.message.answer("Выберите событие для продления серии:", reply_markup=builder.as_markup())
    else:
        await callback.message.answer("У вас пока нет созданных событий.")

@router.callback_query(F.data == "auto_counter")
async def auto_counter(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(counter_type="auto")  #CreateEvent(StatesGroup)
   #                                                        └── waiting_for_event (State)  <-- Пользователь "находится" здесь

                                                        #FSMContext (Память для текущего пользователя):
                                                           #├── Cостояние: CreateEvent.waiting_for_event
                                                           #└── Данные (Data): {"counter_type": "automatic"} <-- Параметр хранится тут
    await callback.message.answer('Напиши название события')
    await state.set_state(CreateEvent.waiting_for_event)

@router.callback_query(F.data == "manual_counter")
async def manual_counter(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(counter_type="manual")
    await callback.message.answer('Напиши название события')
    await state.set_state(CreateEvent.waiting_for_event)

@router.callback_query(DeleteEventCallback.filter())
async def process_delete_event(callback: CallbackQuery, callback_data: DeleteEventCallback, db: UserDatabase):
    target_id = callback_data.event_id
    await db.delete_event(target_id)
    await callback.answer("Событие успешно удалено!")

@router.callback_query(ContinueEventCallback.filter())
async def process_continue_event(callback: CallbackQuery, callback_data: ContinueEventCallback, db: UserDatabase):
    target_id = callback_data.event_id
    if await db.event_continue_streak(target_id):
        await callback.message.answer("Событие успешно продлено!")
    else:
        await callback.message.answer("Ошибка продления!")

@router.message()
async def echo_message(message: Message, db: UserDatabase):
    if message.text and '@' in message.text:
        text = message.text.split()
        words = [i for i in text if '@' in i]
        for word in words:
            #tg_id = None
            #if message.entities:
            #    for entity in message.entities:
            #        if entity.type == "text_mention":  # Если у пользователя нет @username, но его имя кликабельно
            #            tg_id = entity.user.id
            #        elif entity.type == "mention":  # Если это обычный @username
            #            # Для обычного mention нам придется спросить нашу БД,
            #            # успел ли этот @username хоть раз отметиться в боте
            #            tg_id = await db.get_user_by_username(word)
            tg_id =await db.get_user_by_username(word.lower())
            data=await db.get_user(tg_id)
            if data:
                mes=data['auto_answer']
                if mes is None:
                    continue
                else:
                    await message.answer(f'{word} сказал/а: "{mes}"')

if __name__ == "__main__":
    asyncio.run(main())

