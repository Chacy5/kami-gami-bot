import asyncio
import json
import os
import random
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

# =========================
# CONFIG
# =========================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")  # твой chat_id

if not BOT_TOKEN:
    raise RuntimeError("Укажи BOT_TOKEN в .env")

DATA_DIR = Path("./data")
DATA_DIR.mkdir(exist_ok=True)
USERS_FILE = DATA_DIR / "users.json"


# =========================
# БАЗА ДАННЫХ (JSON MVP)
# =========================

def load_users():
    if not USERS_FILE.exists():
        return {}
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_users(users: dict):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


USERS = load_users()


def get_user(user_id: int) -> dict:
    uid = str(user_id)
    if uid not in USERS:
        USERS[uid] = {
            "tokens": {},
            "rp": 0,
            "bp_level": 0,
        }
    return USERS[uid]


def add_tokens(user_id: int, tokens: list[str]):
    user = get_user(user_id)
    tdict = user.setdefault("tokens", {})
    for t in tokens:
        tdict[t] = tdict.get(t, 0) + 1


def get_token_balance_text(user_id: int) -> str:
    user = get_user(user_id)
    tdict = user.get("tokens", {})
    if not tdict:
        return "Пока нет жетонов."
    lines = []
    for token, count in sorted(tdict.items()):
        lines.append(f"{token}: {count}")
    return "\n".join(lines)


# =========================
# Battle Pass
# =========================

RP_PER_LEVEL = 5  # сколько RP нужно для 1 уровня BP

BATTLE_PASS = {
    1: {"tokens": {"HYDR": 1}},
    2: {"tokens": {"CLEAN": 1}},
    3: {"tokens": {"HEART": 1}},
    4: {"tokens": {"FOCUS": 1}},
    5: {"tokens": {"HARM": 1}},
    6: {"tokens": {"ORDER": 1}},
    7: {"tokens": {"HYDR": 1, "HEART": 1}},
    8: {"tokens": {"CLEAN": 1, "ORDER": 1}},
    9: {"tokens": {"MOTION": 1}},
    10: {"real": "Маленькая вкусняшка (до 10₾)"},
    11: {"tokens": {"STUDY": 1}},
    12: {"tokens": {"PLAN": 1}},
    13: {"tokens": {"LOG": 1}},
    14: {"tokens": {"CLEAN": 1, "ORDER": 1}},
    15: {"tokens": {"R-LIFE": 1}},
    16: {"tokens": {"LOG": 1}},
    17: {"tokens": {"HARM": 1}},
    18: {"tokens": {"ENDUR": 1}},
    19: {"tokens": {"ERRAND": 1}},
    20: {"real": "Кофе/чай вне дома (до 10₾)"},
    21: {"tokens": {"R-ORDER": 1}},
    22: {"tokens": {"FIN": 1}},
    23: {"tokens": {"MOTION": 1, "VITAL": 1}},
    24: {"tokens": {"KITCH": 1}},
    25: {"real": "Маленькая MTG-карта (до 5₾)"},
    26: {"tokens": {"STUDY": 1}},
    27: {"tokens": {"HYDR": 2}},
    28: {"tokens": {"R-LIFE": 1}},
    29: {"tokens": {"CLEAN": 1, "ORDER": 1}},
    30: {"real": "Маленький предмет для дома (до 10₾)"},
    31: {"tokens": {"HEART": 2}},
    32: {"tokens": {"ENDUR": 1}},
    33: {"tokens": {"FIN": 1}},
    34: {"tokens": {"FIX": 1}},
    35: {"real": "Вкусняшка/закуска (до 10₾)"},
    36: {"tokens": {"R-LIFE": 1}},
    37: {"tokens": {"R-ORDER": 1}},
    38: {"tokens": {"HARM": 1, "FOCUS": 1}},
    39: {"tokens": {"HEART": 1, "PLAN": 1}},
    40: {"real": "MTG-приз (до 10₾)"},
    41: {"tokens": {"ENDUR": 1}},
    42: {"tokens": {"R-LIFE": 1, "R-ORDER": 1}},
    43: {"tokens": {"HYDR": 2, "MOTION": 1}},
    44: {"tokens": {"PLAN": 1, "FIN": 1}},
    45: {"real": "Выбрать уютный вечер (фильм/игра/еда)"},
    46: {"tokens": {"CLEAN": 2}},
    47: {"tokens": {"R-LIFE": 1}},
    48: {"tokens": {"FOCUS": 1, "STUDY": 1}},
    49: {"tokens": {"ENDUR": 1, "CREAT": 1}},
    50: {"real": "Сезонный MTG-набор (до $50)"},
}


async def give_real_reward_notification(bot: Bot, user_id: int, text: str, source: str):
    # Сообщаем ЕМУ
    await bot.send_message(
        user_id,
        f"🎁 Ты получил реальную награду:\n<b>{text}</b>",
        parse_mode=ParseMode.HTML,
    )

    # Сообщаем ТЕБЕ
    if ADMIN_CHAT_ID:
        await bot.send_message(
            int(ADMIN_CHAT_ID),
            f"🔔 Реальная награда для него:\n<b>{text}</b>\nИсточник: {source}",
            parse_mode=ParseMode.HTML,
        )


async def apply_bp_reward(bot: Bot, user_id: int, level: int):
    reward = BATTLE_PASS.get(level)
    if not reward:
        return

    if "tokens" in reward:
        tokens_dict = reward["tokens"]
        toks = []
        for k, v in tokens_dict.items():
            for _ in range(v):
                toks.append(k)
        add_tokens(user_id, toks)

        await bot.send_message(
            user_id,
            f"🌙 Уровень {level} Battle Pass!\n"
            f"Получены жетоны: " +
            ", ".join(f"{k}×{v}" for k, v in tokens_dict.items())
        )

    elif "real" in reward:
        text = reward["real"]
        await give_real_reward_notification(
            bot,
            user_id,
            text,
            source=f"уровень BP {level}",
        )


async def add_rp_and_check_bp(bot: Bot, user_id: int, rp_amount: int):
    user = get_user(user_id)
    old_rp = user.get("rp", 0)
    user["rp"] = old_rp + rp_amount

    old_level = user.get("bp_level", 0)
    new_level = user["rp"] // RP_PER_LEVEL
    if new_level > 50:
        new_level = 50

    if new_level > old_level:
        for lvl in range(old_level + 1, new_level + 1):
            await apply_bp_reward(bot, user_id, lvl)
        user["bp_level"] = new_level

    save_users(USERS)


# =========================
# КАТАЛОГ ЗАДАЧ
# =========================

TASKS = [
    # EASY
    {
        "id": "easy_water",
        "name": "Выпить стакан воды",
        "type": "easy",
        "rp": 1,
        "tokens": ["HYDR", "HEART"],
        "category": "self",
    },
    {
        "id": "easy_trash",
        "name": "Выбросить мусор",
        "type": "easy",
        "rp": 1,
        "tokens": ["CLEAN"],
        "category": "home",
    },
    {
        "id": "easy_plan",
        "name": "Проверить план на завтра",
        "type": "easy",
        "rp": 1,
        "tokens": ["PLAN"],
        "category": "mind",
    },

    # MEDIUM
    {
        "id": "med_walk",
        "name": "Прогуляться 15 минут",
        "type": "medium",
        "rp": 2,
        "tokens": ["MOTION", "HARM"],
        "category": "body",
    },
    {
        "id": "med_zone",
        "name": "Убрать одну зону дома",
        "type": "medium",
        "rp": 2,
        "tokens": ["CLEAN", "ORDER"],
        "category": "home",
    },
    {
        "id": "med_work30",
        "name": "30 минут работы без телефона",
        "type": "medium",
        "rp": 2,
        "tokens": ["FOCUS", "PLAN"],
        "category": "mind",
    },

    # HARD
    {
        "id": "hard_kitchen",
        "name": "Генерально убрать кухню",
        "type": "hard",
        "rp": 4,
        "tokens": ["CLEAN", "ORDER", "FIX"],
        "category": "home",
    },
    {
        "id": "hard_lifeknot",
        "name": "Закрыть тяжёлый жизненный узел",
        "type": "hard",
        "rp": 4,
        "tokens": ["LOG", "FIX", "ORDER"],
        "category": "life",
    },

    # EPIC
    {
        "id": "epic_flat",
        "name": "Поверхностно убрать всю квартиру",
        "type": "epic",
        "rp": 6,
        "tokens": ["CLEAN", "ORDER", "FIX"],
        "category": "home",
    },

    # JOINT
    {
        "id": "joint_tea",
        "name": "Совместный чай/кофе без телефонов",
        "type": "joint",
        "rp": 2,
        "tokens": ["HEART", "HARM"],
        "category": "joint",
    },
    {
        "id": "joint_movie",
        "name": "Уютный вечер вместе",
        "type": "joint",
        "rp": 3,
        "tokens": ["HEART", "HARM"],
        "category": "joint",
    },

    # MTG
    {
        "id": "mtg_sort",
        "name": "Пересортировать 20 MTG-карт",
        "type": "mtg",
        "rp": 2,
        "tokens": ["ORDER", "LOG"],
        "category": "mtg",
    },
    {
        "id": "mtg_box",
        "name": "Организовать одну MTG-коробку",
        "type": "mtg",
        "rp": 3,
        "tokens": ["ORDER", "LOG", "FIX"],
        "category": "mtg",
    },
]


def get_tasks_by_type(task_type: str):
    return [t for t in TASKS if t["type"] == task_type]


def get_random_task(task_type: str):
    candidates = get_tasks_by_type(task_type)
    return random.choice(candidates) if candidates else None


# =========================
# КРАФТ НАГРАД
# =========================

REWARDS = [
    {
        "id": "small_sweet",
        "name": "Батончик / сладость (до 10₾)",
        "category": "small",
        "cost": {"HEART": 2, "HYDR": 1, "CLEAN": 1},
        "real": True,
    },
    {
        "id": "small_coffee",
        "name": "Кофе вне дома (до 10₾)",
        "category": "small",
        "cost": {"FIN": 1, "HEART": 1, "ERRAND": 1},
        "real": True,
    },
    {
        "id": "mtg_booster",
        "name": "MTG booster",
        "category": "medium",
        "cost": {"STUDY": 1, "ORDER": 1, "FIN": 1},
        "real": True,
    },
    {
        "id": "comfort_evening",
        "name": "Уютный вечер вдвоём",
        "category": "large",
        "cost": {"HEART": 2, "HARM": 1, "R-LIFE": 1},
        "real": True,
    },
]


def get_reward_by_id(rid: str):
    for r in REWARDS:
        if r["id"] == rid:
            return r
    return None


def user_can_afford(user_id: int, reward: dict) -> bool:
    user = get_user(user_id)
    tdict = user.get("tokens", {})
    for token, need in reward["cost"].items():
        if tdict.get(token, 0) < need:
            return False
    return True


def spend_tokens(user_id: int, reward: dict):
    user = get_user(user_id)
    tdict = user.get("tokens", {})
    for token, need in reward["cost"].items():
        tdict[token] = max(0, tdict.get(token, 0) - need)


# =========================
# КЛАВИАТУРЫ
# =========================

def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✨ Ежедневки", callback_data="menu_daily")],
            [InlineKeyboardButton(text="⚗️ Крафт наград", callback_data="menu_craft")],
            [InlineKeyboardButton(text="🌙 Сезон", callback_data="menu_season")],
            [InlineKeyboardButton(text="💞 Совместные", callback_data="menu_joint")],
            [InlineKeyboardButton(text="🃏 MTG", callback_data="menu_mtg")],
            [InlineKeyboardButton(text="⚙️ Профиль", callback_data="menu_profile")],
        ]
    )


def daily_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Лёгкая", callback_data="daily_easy"),
                InlineKeyboardButton(text="Средняя", callback_data="daily_medium"),
            ],
            [
                InlineKeyboardButton(text="Тяжёлая", callback_data="daily_hard"),
                InlineKeyboardButton(text="Эпическая", callback_data="daily_epic"),
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")],
        ]
    )


def task_action_kb(task_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Сделано",
                    callback_data=f"task_done:{task_id}"
                )
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_daily")],
        ]
    )


def craft_menu_kb() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=r["name"],
                callback_data=f"craft:{r['id']}",
            )
        ]
        for r in REWARDS
    ]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def joint_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Лёгкий совместный", callback_data="joint_easy"),
                InlineKeyboardButton(text="Уютный вечер", callback_data="joint_cozy"),
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")],
        ]
    )


def mtg_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="MTG-квест", callback_data="mtg_small"),
                InlineKeyboardButton(text="Организация карт", callback_data="mtg_org"),
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")],
        ]
    )


# =========================
# ROUTER
# =========================

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    get_user(message.from_user.id)
    save_users(USERS)
    await message.answer(
        "Привет! Это твой бытовой Battle Pass.\n"
        "Выполняй задачи → получай RP и награды.\n\n"
        "Выбери действие:",
        reply_markup=main_menu_kb(),
    )


# ---------- MAIN MENU ----------

@router.callback_query(F.data == "back_main")
async def cb_back_main(callback: CallbackQuery):
    await callback.message.edit_text("Главное меню:", reply_markup=main_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "menu_daily")
async def cb_menu_daily(callback: CallbackQuery):
    await callback.message.edit_text("Выбери тип задачи:", reply_markup=daily_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "menu_craft")
async def cb_menu_craft(callback: CallbackQuery):
    await callback.message.edit_text("Награды для крафта:", reply_markup=craft_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "menu_season")
async def cb_menu_season(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    rp = user["rp"]
    bp = user["bp_level"]
    text = (
        "🌕 <b>Season of Lunar Archives</b>\n"
        "Тема: фокус, порядок, спокойствие.\n\n"
        f"Уровень: <b>{bp}</b>/50\n"
        f"RP: <b>{rp}</b>\n\n"
        "Финальная награда: MTG-набор до $50"
    )
    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=main_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "menu_joint")
async def cb_menu_joint(callback: CallbackQuery):
    await callback.message.edit_text(
        "Совместные задачи (выбираются вручную):",
        reply_markup=joint_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "menu_mtg")
async def cb_menu_mtg(callback: CallbackQuery):
    await callback.message.edit_text(
        "MTG-квесты:",
        reply_markup=mtg_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "menu_profile")
async def cb_menu_profile(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    rp = user["rp"]
    bp = user["bp_level"]
    tokens_text = get_token_balance_text(callback.from_user.id)

    text = (
        "👤 <b>Профиль</b>\n\n"
        f"RP: <b>{rp}</b>\n"
        f"Уровень BP: <b>{bp}</b>/50\n\n"
        f"Жетоны:\n{tokens_text}"
    )

    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=main_menu_kb())
    await callback.answer()


# ---------- DAILY TASKS ----------

@router.callback_query(F.data.in_({
    "daily_easy", "daily_medium", "daily_hard", "daily_epic"
}))
async def cb_choose_task(callback: CallbackQuery):
    mapping = {
        "daily_easy": "easy",
        "daily_medium": "medium",
        "daily_hard": "hard",
        "daily_epic": "epic",
    }
    ttype = mapping[callback.data]

    task = get_random_task(ttype)
    if not task:
        await callback.answer("Нет задач этого типа.", show_alert=True)
        return

    text = f"Задача:\n<b>{task['name']}</b>"
    await callback.message.edit_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=task_action_kb(task["id"]),
    )
    await callback.answer()


def get_task_by_id(tid: str):
    for t in TASKS:
        if t["id"] == tid:
            return t
    return None


@router.callback_query(F.data.startswith("task_done:"))
async def cb_task_done(callback: CallbackQuery, bot: Bot):
    tid = callback.data.split(":", 1)[1]
    task = get_task_by_id(tid)
    if not task:
        await callback.answer("Задача не найдена.", show_alert=True)
        return

    user_id = callback.from_user.id
    add_tokens(user_id, task["tokens"])
    await add_rp_and_check_bp(bot, user_id, task["rp"])

    tokens_text = ", ".join(task["tokens"])
    text = (
        f"✅ Задача выполнена:\n<b>{task['name']}</b>\n\n"
        f"+{task['rp']} RP\n"
        f"Жетоны: {tokens_text}"
    )
    await callback.message.edit_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=daily_menu_kb(),
    )
    await callback.answer("Готово!")


# ---------- JOINT TASKS ----------

@router.callback_query(F.data == "joint_easy")
async def cb_joint_easy(callback: CallbackQuery, bot: Bot):
    task = get_task_by_id("joint_tea")
    user_id = callback.from_user.id

    add_tokens(user_id, task["tokens"])
    await add_rp_and_check_bp(bot, user_id, task["rp"])

    toks = ", ".join(task["tokens"])
    text = (
        f"💞 Совместный лёгкий квест:\n<b>{task['name']}</b>\n\n"
        f"+{task['rp']} RP\nЖетоны: {toks}"
    )

    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=joint_menu_kb())
    await callback.answer("Совместный момент записан 💞")


@router.callback_query(F.data == "joint_cozy")
async def cb_joint_cozy(callback: CallbackQuery, bot: Bot):
    task = get_task_by_id("joint_movie")
    user_id = callback.from_user.id

    add_tokens(user_id, task["tokens"])
    await add_rp_and_check_bp(bot, user_id, task["rp"])

    toks = ", ".join(task["tokens"])
    text = (
        f"💞 Уютный вечер-квест:\n<b>{task['name']}</b>\n\n"
        f"+{task['rp']} RP\nЖетоны: {toks}"
    )

    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=joint_menu_kb())
    await callback.answer("Записано ✨")


# ---------- MTG TASKS ----------

@router.callback_query(F.data == "mtg_small")
async def cb_mtg_small(callback: CallbackQuery, bot: Bot):
    task = get_task_by_id("mtg_sort")
    user_id = callback.from_user.id

    add_tokens(user_id, task["tokens"])
    await add_rp_and_check_bp(bot, user_id, task["rp"])

    toks = ", ".join(task["tokens"])
    text = (
        f"🃏 MTG-квест:\n<b>{task['name']}</b>\n\n"
        f"+{task['rp']} RP\nЖетоны: {toks}"
    )

    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=mtg_menu_kb())
    await callback.answer("Карты стали ещё аккуратнее 🃏")


@router.callback_query(F.data == "mtg_org")
async def cb_mtg_org(callback: CallbackQuery, bot: Bot):
    task = get_task_by_id("mtg_box")
    user_id = callback.from_user.id

    add_tokens(user_id, task["tokens"])
    await add_rp_and_check_bp(bot, user_id, task["rp"])

    toks = ", ".join(task["tokens"])
    text = (
        f"🃏 MTG-организация:\n<b>{task['name']}</b>\n\n"
        f"+{task['rp']} RP\nЖетоны: {toks}"
    )

    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=mtg_menu_kb())
    await callback.answer("MTG-порядок становится сильнее ✨")


# ---------- CRAFT ----------

@router.callback_query(F.data.startswith("craft:"))
async def cb_craft(callback: CallbackQuery, bot: Bot):
    rid = callback.data.split(":", 1)[1]
    reward = get_reward_by_id(rid)
    if not reward:
        await callback.answer("Награда не найдена.", show_alert=True)
        return

    user_id = callback.from_user.id
    if not user_can_afford(user_id, reward):
        await callback.answer("Не хватает жетонов.", show_alert=True)
        return

    spend_tokens(user_id, reward)
    save_users(USERS)

    if reward.get("real"):
        await give_real_reward_notification(
            bot,
            user_id,
            reward["name"],
            source=f"крафт '{reward['id']}'",
        )
        text = (
            f"🎁 Ты скрафтил реальную награду:\n<b>{reward['name']}</b>\n\n"
            "Small v получит уведомление выдать её ❤️"
        )
    else:
        text = f"✨ Награда создана: <b>{reward['name']}</b>"

    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=craft_menu_kb())
    await callback.answer("Награда зафиксирована!")


# =========================
# MAIN
# =========================

async def main():
    bot = Bot(
        BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher()
    dp.include_router(router)

    print("Bot started...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
