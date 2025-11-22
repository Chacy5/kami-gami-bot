import asyncio
import json
import os
from pathlib import Path
from collections import Counter
from datetime import datetime

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

# Конец сезона (можешь поменять под себя)
SEASON_END = datetime(2026, 1, 31)  # ГГГГ, ММ, ДД

# Сколько RP нужно для 1 уровня BP
RP_PER_LEVEL = 5

# Эмодзи для эмблем
TOKEN_EMOJI = {
    "HYDR": "💧",
    "HEART": "❤️",
    "HARM": "🧠",
    "ORDER": "🧱",
    "CLEAN": "🧼",
    "MOTION": "🚶",
    "STUDY": "📚",
    "PLAN": "📅",
    "LOG": "📝",
    "R-LIFE": "✨",
    "R-ORDER": "🧩",
    "ERRAND": "🏃",
    "FIN": "💰",
    "KITCH": "🍽️",
    "ENDUR": "💪",
    "CARE": "🐾",
    "VITAL": "⚡",
    "FIX": "🔧",
    "CREAT": "🎨",
}

# Чтобы сортировать по эмблемам — список ключей
TOKEN_LIST = list(TOKEN_EMOJI.keys())


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
            "search_mode": None,  # task_search / reward_search
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
        return "Пока нет эмблем."
    lines = []
    for token, count in sorted(tdict.items()):
        emoji = TOKEN_EMOJI.get(token, "🔸")
        lines.append(f"{emoji} — {count}")
    return "\n".join(lines)


def format_task_tokens_award(tokens: list[str]) -> str:
    """Эмблемы за задачу: 💧×2 🧼"""
    if not tokens:
        return "нет"
    c = Counter(tokens)
    parts = []
    for token, cnt in c.items():
        emoji = TOKEN_EMOJI.get(token, "🔸")
        if cnt > 1:
            parts.append(f"{emoji}×{cnt}")
        else:
            parts.append(f"{emoji}")
    return " ".join(parts)


def format_token_balance_for_user(user_id: int, token: str, required: int) -> str:
    """Для крафта: ✅💧5/5 или ▫️💧3/10"""
    user = get_user(user_id)
    have = user.get("tokens", {}).get(token, 0)
    emoji = TOKEN_EMOJI.get(token, "🔸")
    if have >= required:
        return f"✅{emoji}{have}/{required}"
    else:
        return f"▫️{emoji}{have}/{required}"


def get_season_countdown_text() -> str:
    now = datetime.now()
    delta = SEASON_END - now
    days = delta.days
    if days <= 0:
        return "Сезон завершён."
    weeks = days // 7
    rem_days = days % 7
    parts = []
    if weeks > 0:
        parts.append(f"{weeks} нед.")
    if rem_days > 0:
        parts.append(f"{rem_days} дн.")
    return "До конца сезона: " + " ".join(parts)


# =========================
# Battle Pass
# =========================

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
    45: {"real": "Уютный вечер (фильм/игра/еда)"},
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

        pretty = []
        for token, v in tokens_dict.items():
            emoji = TOKEN_EMOJI.get(token, "🔸")
            if v > 1:
                pretty.append(f"{emoji}×{v}")
            else:
                pretty.append(f"{emoji}")
        await bot.send_message(
            user_id,
            f"🌙 Уровень {level} Battle Pass!\n"
            f"Эмблемы: {' '.join(pretty)}"
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
# КАТАЛОГ ЗАДАЧ (~95)
# =========================

TASKS = [
    # =========================
    # EASY — лёгкие (RP = 1)
    # =========================
    {
        "id": "easy_water",
        "name": "Выпить стакан воды",
        "type": "easy",
        "rp": 1,
        "tokens": ["HYDR", "HEART"],
        "category": "self",
    },
    {
        "id": "easy_breath",
        "name": "Сделать 10 глубоких вдохов",
        "type": "easy",
        "rp": 1,
        "tokens": ["HARM"],
        "category": "self",
    },
    {
        "id": "easy_facewash",
        "name": "Помыть лицо или сделать базовый уход",
        "type": "easy",
        "rp": 1,
        "tokens": ["HEART"],
        "category": "self",
    },
    {
        "id": "easy_tea_slow",
        "name": "Выпить чай или кофе не впопыхах",
        "type": "easy",
        "rp": 1,
        "tokens": ["HEART", "HARM"],
        "category": "self",
    },
    {
        "id": "easy_prep_drink",
        "name": "Приготовить воду или чай на завтра",
        "type": "easy",
        "rp": 1,
        "tokens": ["PLAN"],
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
        "id": "easy_clothes_stack",
        "name": "Сложить одежду в одном месте",
        "type": "easy",
        "rp": 1,
        "tokens": ["CLEAN", "ORDER"],
        "category": "home",
    },
    {
        "id": "easy_wipe_small",
        "name": "Протереть одну маленькую поверхность",
        "type": "easy",
        "rp": 1,
        "tokens": ["CLEAN"],
        "category": "home",
    },
    {
        "id": "easy_mini_pile",
        "name": "Разобрать одну мини-свалку",
        "type": "easy",
        "rp": 1,
        "tokens": ["ORDER"],
        "category": "home",
    },
    {
        "id": "easy_trashbag",
        "name": "Поменять пакет в мусорке",
        "type": "easy",
        "rp": 1,
        "tokens": ["CLEAN"],
        "category": "home",
    },

    {
        "id": "easy_laundry_step",
        "name": "Сделать один шаг стирки (запустить/развесить/убрать)",
        "type": "easy",
        "rp": 1,
        "tokens": ["CLEAN", "ORDER"],
        "category": "home",
    },
    {
        "id": "easy_check_supplies",
        "name": "Проверить бытовые расходники (бумага, мыло и т.п.)",
        "type": "easy",
        "rp": 1,
        "tokens": ["LOG"],
        "category": "home",
    },
    {
        "id": "easy_put_5_items",
        "name": "Убрать 5 вещей на свои места",
        "type": "easy",
        "rp": 1,
        "tokens": ["ORDER"],
        "category": "home",
    },
    {
        "id": "easy_shoes",
        "name": "Почистить или убрать обувь",
        "type": "easy",
        "rp": 1,
        "tokens": ["CLEAN"],
        "category": "home",
    },
    {
        "id": "easy_towel",
        "name": "Заменить полотенце или кухонную тряпку",
        "type": "easy",
        "rp": 1,
        "tokens": ["CLEAN"],
        "category": "home",
    },

    {
        "id": "easy_buy_small",
        "name": "Купить одну нужную мелочь",
        "type": "easy",
        "rp": 1,
        "tokens": ["ERRAND"],
        "category": "life",
    },
    {
        "id": "easy_pay_small",
        "name": "Сделать мелкую оплату или пополнить баланс",
        "type": "easy",
        "rp": 1,
        "tokens": ["FIN"],
        "category": "life",
    },
    {
        "id": "easy_parcel",
        "name": "Отнести или получить посылку",
        "type": "easy",
        "rp": 1,
        "tokens": ["ERRAND", "MOTION"],
        "category": "life",
    },
    {
        "id": "easy_shop_short",
        "name": "Сходить в магазин за 1–3 предметами",
        "type": "easy",
        "rp": 1,
        "tokens": ["ERRAND"],
        "category": "life",
    },
    {
        "id": "easy_check_plan",
        "name": "Проверить план на завтра",
        "type": "easy",
        "rp": 1,
        "tokens": ["PLAN"],
        "category": "mind",
    },

    {
        "id": "easy_read_page",
        "name": "Прочитать одну страницу",
        "type": "easy",
        "rp": 1,
        "tokens": ["STUDY"],
        "category": "mind",
    },
    {
        "id": "easy_reply_msg",
        "name": "Ответить на одно важное сообщение",
        "type": "easy",
        "rp": 1,
        "tokens": ["FOCUS"],
        "category": "mind",
    },
    {
        "id": "easy_desk",
        "name": "Немного прибрать рабочий стол",
        "type": "easy",
        "rp": 1,
        "tokens": ["ORDER", "FOCUS"],
        "category": "mind",
    },
    {
        "id": "easy_small_worktask",
        "name": "Сделать одну мини-задачу по работе (до 5 минут)",
        "type": "easy",
        "rp": 1,
        "tokens": ["FOCUS"],
        "category": "mind",
    },
    {
        "id": "easy_no_phone_10",
        "name": "10 минут без телефона",
        "type": "easy",
        "rp": 1,
        "tokens": ["HARM"],
        "category": "self",
    },

    {
        "id": "easy_dog_pet",
        "name": "Спокойно почесать или погладить собаку",
        "type": "easy",
        "rp": 1,
        "tokens": ["HEART", "CARE"],
        "category": "dog",
    },
    {
        "id": "easy_silence_5",
        "name": "5 минут тишины",
        "type": "easy",
        "rp": 1,
        "tokens": ["HARM"],
        "category": "self",
    },
    {
        "id": "easy_dog_feed",
        "name": "Накормить собаку по расписанию",
        "type": "easy",
        "rp": 1,
        "tokens": ["CARE"],
        "category": "dog",
    },
    {
        "id": "easy_self_nice",
        "name": "Сделать один маленький добрый жест для себя",
        "type": "easy",
        "rp": 1,
        "tokens": ["HEART"],
        "category": "self",
    },
    {
        "id": "easy_log_one",
        "name": "Записать одну вещь в долгий список задач/идей",
        "type": "easy",
        "rp": 1,
        "tokens": ["LOG"],
        "category": "mind",
    },

    # =========================
    # MEDIUM — средние (RP = 2)
    # =========================
    {
        "id": "med_water_2l",
        "name": "Выпить примерно 2 литра воды за день",
        "type": "medium",
        "rp": 2,
        "tokens": ["HYDR", "HEART", "ENDUR"],
        "category": "self",
    },
    {
        "id": "med_shower_ritual",
        "name": "Принять душ как маленький ритуал ухода",
        "type": "medium",
        "rp": 2,
        "tokens": ["HEART", "HARM"],
        "category": "self",
    },
    {
        "id": "med_morning_care",
        "name": "Сделать полный утренний уход",
        "type": "medium",
        "rp": 2,
        "tokens": ["HEART", "CLEAN"],
        "category": "self",
    },
    {
        "id": "med_walk_15",
        "name": "Прогуляться 15+ минут",
        "type": "medium",
        "rp": 2,
        "tokens": ["MOTION", "HARM"],
        "category": "body",
    },
    {
        "id": "med_stretch",
        "name": "Сделать лёгкую растяжку 5–10 минут",
        "type": "medium",
        "rp": 2,
        "tokens": ["MOTION", "ENDUR"],
        "category": "body",
    },

    {
        "id": "med_clean_zone",
        "name": "Убрать одну зону дома среднего размера",
        "type": "medium",
        "rp": 2,
        "tokens": ["CLEAN", "ORDER"],
        "category": "home",
    },
    {
        "id": "med_kitchen_wipe",
        "name": "Протереть кухню полностью (поверхности)",
        "type": "medium",
        "rp": 2,
        "tokens": ["CLEAN", "FIX"],
        "category": "home",
    },
    {
        "id": "med_laundry_full",
        "name": "Сделать полный цикл стирки (от запуска до уборки)",
        "type": "medium",
        "rp": 2,
        "tokens": ["CLEAN", "ORDER", "ENDUR"],
        "category": "home",
    },
    {
        "id": "med_shelf",
        "name": "Разобрать одну полку или ящик",
        "type": "medium",
        "rp": 2,
        "tokens": ["ORDER", "LOG"],
        "category": "home",
    },
    {
        "id": "med_problem_spot",
        "name": "Разобрать один «проблемный» угол/участок",
        "type": "medium",
        "rp": 2,
        "tokens": ["ORDER", "CLEAN"],
        "category": "home",
    },

    {
        "id": "med_big_shopping",
        "name": "Сделать покупки на несколько дней (5+ позиций)",
        "type": "medium",
        "rp": 2,
        "tokens": ["ERRAND", "FIN", "MOTION"],
        "category": "life",
    },
    {
        "id": "med_bureaucracy",
        "name": "Сделать одну бюрократическую задачу",
        "type": "medium",
        "rp": 2,
        "tokens": ["FIN", "LOG"],
        "category": "life",
    },
    {
        "id": "med_inbox_10",
        "name": "Разобрать 10+ сообщений или писем",
        "type": "medium",
        "rp": 2,
        "tokens": ["FOCUS", "LOG"],
        "category": "mind",
    },
    {
        "id": "med_buy_from_list",
        "name": "Обновить список покупок и купить 1 вещь из него",
        "type": "medium",
        "rp": 2,
        "tokens": ["PLAN", "ERRAND"],
        "category": "life",
    },
    {
        "id": "med_one_old_task",
        "name": "Сделать одну давно отложенную задачу",
        "type": "medium",
        "rp": 2,
        "tokens": ["FOCUS", "ORDER", "LOG"],
        "category": "life",
    },

    {
        "id": "med_work_30",
        "name": "30 минут работы без телефона",
        "type": "medium",
        "rp": 2,
        "tokens": ["FOCUS", "PLAN"],
        "category": "mind",
    },
    {
        "id": "med_prep_lessons",
        "name": "Подготовить уроки или работу на завтра",
        "type": "medium",
        "rp": 2,
        "tokens": ["PLAN", "STUDY"],
        "category": "mind",
    },
    {
        "id": "med_read_10pages",
        "name": "Прочитать 5–10 страниц",
        "type": "medium",
        "rp": 2,
        "tokens": ["STUDY", "FOCUS"],
        "category": "mind",
    },
    {
        "id": "med_plan_tomorrow",
        "name": "Составить план на завтра (3–5 пунктов)",
        "type": "medium",
        "rp": 2,
        "tokens": ["PLAN", "LOG"],
        "category": "mind",
    },
    {
        "id": "med_desk_10min",
        "name": "10 минут на порядок в рабочей зоне",
        "type": "medium",
        "rp": 2,
        "tokens": ["ORDER", "FOCUS"],
        "category": "mind",
    },

    {
        "id": "med_dog_quality",
        "name": "Провести особое качественное время с собакой",
        "type": "medium",
        "rp": 2,
        "tokens": ["CARE", "HEART"],
        "category": "dog",
    },
    {
        "id": "med_dog_longwalk",
        "name": "Сделать прогулку с собакой дольше обычного",
        "type": "medium",
        "rp": 2,
        "tokens": ["CARE", "MOTION"],
        "category": "dog",
    },
    {
        "id": "med_self_buy",
        "name": "Купить маленькую полезную вещь для себя",
        "type": "medium",
        "rp": 2,
        "tokens": ["HEART", "FIN"],
        "category": "self",
    },
    {
        "id": "med_life_knot_small",
        "name": "Решить один маленький жизненный узел",
        "type": "medium",
        "rp": 2,
        "tokens": ["FIX", "ORDER", "CLEAN"],
        "category": "life",
    },
    {
        "id": "med_home_improve",
        "name": "Сделать шаг, который улучшает дом (организация, крючок и т.п.)",
        "type": "medium",
        "rp": 2,
        "tokens": ["FIX", "ORDER", "LOG"],
        "category": "home",
    },

    # =========================
    # HARD — сложные (RP = 4)
    # =========================
    {
        "id": "hard_big_zone",
        "name": "Разобрать большую зону (коробка, большой ящик или угол)",
        "type": "hard",
        "rp": 4,
        "tokens": ["ORDER", "CLEAN", "LOG"],
        "category": "home",
    },
    {
        "id": "hard_kitchen_general",
        "name": "Генерально убрать кухню",
        "type": "hard",
        "rp": 4,
        "tokens": ["CLEAN", "FIX", "ORDER"],
        "category": "home",
    },
    {
        "id": "hard_bath_clean",
        "name": "Хорошо почистить ванну или душевую",
        "type": "hard",
        "rp": 4,
        "tokens": ["CLEAN", "FIX"],
        "category": "home",
    },
    {
        "id": "hard_bag_clothes",
        "name": "Разобрать большой мешок или коробку с вещами",
        "type": "hard",
        "rp": 4,
        "tokens": ["ORDER", "CLEAN"],
        "category": "home",
    },
    {
        "id": "hard_storage_system",
        "name": "Организовать одну зону хранения по нормальной системе",
        "type": "hard",
        "rp": 4,
        "tokens": ["ORDER", "LOG", "FIX"],
        "category": "home",
    },

    {
        "id": "hard_huge_shopping",
        "name": "Сделать большой закуп (15–20+ позиций)",
        "type": "hard",
        "rp": 4,
        "tokens": ["FIN", "ERRAND", "MOTION"],
        "category": "life",
    },
    {
        "id": "hard_walk_45",
        "name": "Прогуляться 45+ минут",
        "type": "hard",
        "rp": 4,
        "tokens": ["MOTION", "ENDUR", "HARM"],
        "category": "body",
    },
    {
        "id": "hard_city_quest",
        "name": "Сделать сложный бытовой квест вне дома",
        "type": "hard",
        "rp": 4,
        "tokens": ["ERRAND", "FIN", "LOG"],
        "category": "life",
    },
    {
        "id": "hard_work_90",
        "name": "1,5 часа работы без телефона",
        "type": "hard",
        "rp": 4,
        "tokens": ["FOCUS", "PLAN"],
        "category": "mind",
    },
    {
        "id": "hard_lessons_multi",
        "name": "Подготовить несколько уроков/задач вперёд",
        "type": "hard",
        "rp": 4,
        "tokens": ["STUDY", "PLAN", "FOCUS"],
        "category": "mind",
    },

    {
        "id": "hard_inbox_20",
        "name": "Разобрать 20+ писем, файлов или задач",
        "type": "hard",
        "rp": 4,
        "tokens": ["FOCUS", "ORDER", "LOG"],
        "category": "mind",
    },
    {
        "id": "hard_care_ritual",
        "name": "Сделать активный уход за собой 20+ минут",
        "type": "hard",
        "rp": 4,
        "tokens": ["HEART", "HARM", "ENDUR"],
        "category": "self",
    },
    {
        "id": "hard_silence_20",
        "name": "20 минут осознанной тишины или медитации",
        "type": "hard",
        "rp": 4,
        "tokens": ["HARM", "FOCUS"],
        "category": "self",
    },
    {
        "id": "hard_dog_bigwalk",
        "name": "Большая прогулка с собакой (30+ минут)",
        "type": "hard",
        "rp": 4,
        "tokens": ["CARE", "MOTION", "HARM"],
        "category": "dog",
    },
    {
        "id": "hard_life_knot_big",
        "name": "Разобрать один тяжёлый жизненный узел",
        "type": "hard",
        "rp": 4,
        "tokens": ["LOG", "FIX", "ORDER"],
        "category": "life",
    },

    # =========================
    # EPIC — эпические (RP = 6)
    # =========================
    {
        "id": "epic_flat_surface",
        "name": "Поверхностно убрать всю квартиру",
        "type": "epic",
        "rp": 6,
        "tokens": ["CLEAN", "ORDER", "FIX"],
        "category": "home",
    },
    {
        "id": "epic_storage_full",
        "name": "Полностью разобрать одну крупную зону хранения",
        "type": "epic",
        "rp": 6,
        "tokens": ["ORDER", "LOG", "FIX"],
        "category": "home",
    },
    {
        "id": "epic_city_marathon",
        "name": "Сделать большую активность по делам вне дома (несколько точек)",
        "type": "epic",
        "rp": 6,
        "tokens": ["MOTION", "ERRAND", "ENDUR"],
        "category": "life",
    },
    {
        "id": "epic_work_2h",
        "name": "2 часа работы или учёбы без телефона",
        "type": "epic",
        "rp": 6,
        "tokens": ["STUDY", "PLAN", "FOCUS"],
        "category": "mind",
    },
    {
        "id": "epic_life_reset",
        "name": "Закрыть один тяжёлый личный или финансовый «узел»",
        "type": "epic",
        "rp": 6,
        "tokens": ["LOG", "FIX", "ORDER", "FIN"],
        "category": "life",
    },

    # =========================
    # JOINT — совместные (RP = 2–4)
    # =========================
    {
        "id": "joint_tea_10",
        "name": "Совместный чай/кофе без телефонов (10 минут)",
        "type": "joint",
        "rp": 2,
        "tokens": ["HEART", "HARM"],
        "category": "joint",
    },
    {
        "id": "joint_silence_5",
        "name": "Совместная тихая пауза 5 минут",
        "type": "joint",
        "rp": 2,
        "tokens": ["HEART", "FOCUS"],
        "category": "joint",
    },
    {
        "id": "joint_dog_walk_short",
        "name": "Короткая совместная прогулка с собакой",
        "type": "joint",
        "rp": 2,
        "tokens": ["CARE", "MOTION"],
        "category": "joint",
    },
    {
        "id": "joint_small_clean",
        "name": "Убрать маленькую зону вместе",
        "type": "joint",
        "rp": 3,
        "tokens": ["CLEAN", "ORDER"],
        "category": "joint",
    },
    {
        "id": "joint_cook_simple",
        "name": "Приготовить вместе что-то простое или перекус",
        "type": "joint",
        "rp": 3,
        "tokens": ["KITCH", "HEART"],
        "category": "joint",
    },

    {
        "id": "joint_sort_stuff",
        "name": "Вместе разобрать один узел вещей",
        "type": "joint",
        "rp": 3,
        "tokens": ["ORDER", "FIX"],
        "category": "joint",
    },
    {
        "id": "joint_cozy_evening",
        "name": "Уютный вечер вместе (фильм/игра/чай)",
        "type": "joint",
        "rp": 3,
        "tokens": ["HEART", "HARM"],
        "category": "joint",
    },
    {
        "id": "joint_city_miniquest",
        "name": "Совместный мини-квест вне дома",
        "type": "joint",
        "rp": 4,
        "tokens": ["ERRAND", "MOTION"],
        "category": "joint",
    },
    {
        "id": "joint_big_storage",
        "name": "Вместе разобрать большую зону хранения",
        "type": "joint",
        "rp": 4,
        "tokens": ["ORDER", "LOG", "FIX"],
        "category": "joint",
    },
    {
        "id": "joint_life_knot_out",
        "name": "Вместе закрыть один жизненный узел вне дома",
        "type": "joint",
        "rp": 4,
        "tokens": ["ERRAND", "FIN", "HEART"],
        "category": "joint",
    },

    # =========================
    # MTG — совместные MTG-квесты (RP = 2–4)
    # =========================
    {
        "id": "mtg_sort_20",
        "name": "Пересортировать вместе 20 карт MTG",
        "type": "mtg",
        "rp": 2,
        "tokens": ["ORDER", "LOG"],
        "category": "mtg",
    },
    {
        "id": "mtg_pick_favorites",
        "name": "Выбрать 5 любимых карт сезона и сложить отдельно",
        "type": "mtg",
        "rp": 2,
        "tokens": ["HEART", "STUDY"],
        "category": "mtg",
    },
    {
        "id": "mtg_watch_video",
        "name": "Посмотреть вместе одно MTG-видео",
        "type": "mtg",
        "rp": 2,
        "tokens": ["STUDY", "HEART"],
        "category": "mtg",
    },
    {
        "id": "mtg_box_organize",
        "name": "Организовать одну коробку с картами",
        "type": "mtg",
        "rp": 3,
        "tokens": ["ORDER", "LOG", "FIX"],
        "category": "mtg",
    },
    {
        "id": "mtg_clean_mat",
        "name": "Почистить стол или коврик для MTG",
        "type": "mtg",
        "rp": 3,
        "tokens": ["CLEAN", "ORDER"],
        "category": "mtg",
    },

    {
        "id": "mtg_choose_deck",
        "name": "Выбрать «колоду сезона» и подготовить её",
        "type": "mtg",
        "rp": 3,
        "tokens": ["LOG", "STUDY"],
        "category": "mtg",
    },
    {
        "id": "mtg_catalog_10",
        "name": "Добавить 10 карт в каталог/список",
        "type": "mtg",
        "rp": 3,
        "tokens": ["ORDER", "LOG"],
        "category": "mtg",
    },
    {
        "id": "mtg_mini_commander",
        "name": "Сделать мини-вечер коммандера (разбор карт/идей)",
        "type": "mtg",
        "rp": 4,
        "tokens": ["HEART", "STUDY", "FOCUS"],
        "category": "mtg",
    },
    {
        "id": "mtg_inventory_clean",
        "name": "Навести порядок в MTG-инвентаре",
        "type": "mtg",
        "rp": 4,
        "tokens": ["ORDER", "CLEAN", "FIX"],
        "category": "mtg",
    },
    {
        "id": "mtg_lunar_slots",
        "name": "Добавить 5 новых слотов в условную «лунную» колоду",
        "type": "mtg",
        "rp": 4,
        "tokens": ["CREAT", "STUDY", "LOG"],
        "category": "mtg",
    },
]

CATEGORIES = {
    "self": "Про себя / self-care",
    "home": "Дом",
    "life": "Жизнь / дела",
    "mind": "Голова / план",
    "body": "Тело / движение",
    "dog": "Собака",
    "joint": "Совместные",
    "mtg": "MTG",
}


def get_tasks_by_type(task_type: str):
    return [t for t in TASKS if t["type"] == task_type]


def get_tasks_by_category(category: str):
    return [t for t in TASKS if t["category"] == category]


def get_tasks_by_token(token: str):
    return [t for t in TASKS if token in t["tokens"]]


def get_task_by_id(tid: str):
    for t in TASKS:
        if t["id"] == tid:
            return t
    return None


# =========================
# КРАФТ НАГРАД
# =========================

REWARDS = [
    # SMALL
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
        "id": "small_home_snack",
        "name": "Маленькая вкусняшка домой",
        "category": "small",
        "cost": {"HEART": 1, "KITCH": 1},
        "real": True,
    },
    {
        "id": "small_desk_item",
        "name": "Мелочь для рабочего стола",
        "category": "small",
        "cost": {"ORDER": 1, "FOCUS": 1},
        "real": True,
    },

    # MEDIUM
    {
        "id": "med_delivery_small",
        "name": "Небольшая доставка еды",
        "category": "medium",
        "cost": {"FIN": 2, "ERRAND": 1, "KITCH": 1},
        "real": True,
    },
    {
        "id": "med_self_buy",
        "name": "Маленькая покупка для себя (до 20₾)",
        "category": "medium",
        "cost": {"HEART": 1, "FIN": 2},
        "real": True,
    },
    {
        "id": "med_home_item",
        "name": "Небольшой предмет для дома (до 20₾)",
        "category": "medium",
        "cost": {"ORDER": 2, "FIX": 1, "FIN": 1},
        "real": True,
    },
    {
        "id": "med_care",
        "name": "Уходовая штука (гель/скраб/маска)",
        "category": "medium",
        "cost": {"HEART": 2, "FIN": 1},
        "real": True,
    },
    {
        "id": "med_mtg_booster",
        "name": "MTG booster",
        "category": "medium",
        "cost": {"STUDY": 1, "ORDER": 1, "FIN": 1},
        "real": True,
    },
    {
        "id": "med_game_small",
        "name": "Небольшая покупка в Steam / DLC (до 20₾)",
        "category": "medium",
        "cost": {"STUDY": 1, "FOCUS": 1, "FIN": 2},
        "real": True,
    },

    # LARGE
    {
        "id": "large_mtg_set",
        "name": "MTG мини-набор (2–3 бустера)",
        "category": "large",
        "cost": {"STUDY": 2, "ORDER": 1, "R-LIFE": 1},
        "real": True,
    },
    {
        "id": "large_delivery_big",
        "name": "Крупная доставка еды",
        "category": "large",
        "cost": {"FIN": 2, "ERRAND": 1, "KITCH": 1, "R-LIFE": 1},
        "real": True,
    },
    {
        "id": "large_home_upgrade",
        "name": "Апгрейд дома (полка, короб, органайзер)",
        "category": "large",
        "cost": {"ORDER": 2, "FIX": 2, "R-ORDER": 1},
        "real": True,
    },
    {
        "id": "large_hobby_item",
        "name": "Покупка для хобби (до 40₾)",
        "category": "large",
        "cost": {"CREAT": 1, "FIN": 2, "R-LIFE": 1},
        "real": True,
    },
    {
        "id": "large_cozy_evening",
        "name": "Уютный вечер «что угодно»",
        "category": "large",
        "cost": {"HEART": 2, "HARM": 1, "R-LIFE": 1},
        "real": True,
    },

    # EPIC
    {
        "id": "epic_mtg_50",
        "name": "MTG набор до 50₾",
        "category": "epic",
        "cost": {"R-LIFE": 2, "R-ORDER": 1, "STUDY": 1, "FIN": 1},
        "real": True,
    },
    {
        "id": "epic_steam_game",
        "name": "Игра в Steam (до 40–50₾)",
        "category": "epic",
        "cost": {"FOCUS": 1, "STUDY": 1, "FIN": 2, "R-LIFE": 1},
        "real": True,
    },
    {
        "id": "epic_home_big",
        "name": "Крупный предмет для дома",
        "category": "epic",
        "cost": {"ORDER": 2, "FIX": 2, "R-ORDER": 2},
        "real": True,
    },
    {
        "id": "epic_big_gift",
        "name": "Большой подарок-сюрприз от тебя",
        "category": "epic",
        "cost": {"HEART": 2, "R-LIFE": 2, "R-ORDER": 1},
        "real": True,
    },

    # LEGENDARY
    {
        "id": "leg_tech",
        "name": "Крупная техника",
        "category": "legendary",
        "cost": {"FIN": 3, "FIX": 2, "R-LIFE": 2, "R-ORDER": 1},
        "real": True,
    },
    {
        "id": "leg_mtg_premium",
        "name": "Премиальный MTG-продукт",
        "category": "legendary",
        "cost": {"STUDY": 2, "CREAT": 1, "R-LIFE": 2, "R-ORDER": 2},
        "real": True,
    },
    {
        "id": "leg_trip",
        "name": "Мини-поездка / событие",
        "category": "legendary",
        "cost": {"MOTION": 1, "FIN": 3, "R-LIFE": 2, "R-ORDER": 1},
        "real": True,
    },
    {
        "id": "leg_big_love_gift",
        "name": "Большой подарок от тебя",
        "category": "legendary",
        "cost": {"HEART": 3, "R-LIFE": 2, "R-ORDER": 2},
        "real": True,
    },
]


def get_reward_by_id(rid: str):
    for r in REWARDS:
        if r["id"] == rid:
            return r
    return None


def get_rewards_by_category(cat: str):
    return [r for r in REWARDS if r["category"] == cat]


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
            [InlineKeyboardButton(text="✨ Задачи", callback_data="menu_daily")],
            [InlineKeyboardButton(text="⚗️ Крафт наград", callback_data="menu_craft")],
            [InlineKeyboardButton(text="🌙 Сезон", callback_data="menu_season")],
            [InlineKeyboardButton(text="🎁 Награды батл-паса", callback_data="bp_rewards")],
            [InlineKeyboardButton(text="💞 Совместные", callback_data="menu_joint")],
            [InlineKeyboardButton(text="🃏 MTG", callback_data="menu_mtg")],
            [InlineKeyboardButton(text="⚙️ Профиль", callback_data="menu_profile")],
        ]
    )


def daily_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="По сложности", callback_data="daily_by_type"),
            ],
            [
                InlineKeyboardButton(text="По категориям", callback_data="daily_by_cat"),
            ],
            [
                InlineKeyboardButton(text="По эмблемам", callback_data="daily_by_token"),
            ],
            [
                InlineKeyboardButton(text="Поиск 🔍", callback_data="daily_search"),
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")],
        ]
    )


def daily_type_select_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Лёгкие", callback_data="daily_easy"),
                InlineKeyboardButton(text="Средние", callback_data="daily_medium"),
            ],
            [
                InlineKeyboardButton(text="Сложные", callback_data="daily_hard"),
                InlineKeyboardButton(text="Эпические", callback_data="daily_epic"),
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_daily")],
        ]
    )


def categories_kb() -> InlineKeyboardMarkup:
    rows = []
    for key, label in CATEGORIES.items():
        rows.append([
            InlineKeyboardButton(
                text=label,
                callback_data=f"daily_cat:{key}:0"
            )
        ])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_daily")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def token_filter_kb() -> InlineKeyboardMarkup:
    rows = []
    for token in TOKEN_LIST:
        emoji = TOKEN_EMOJI.get(token, "🔸")
        rows.append([
            InlineKeyboardButton(
                text=emoji,
                callback_data=f"daily_token:{token}:0"
            )
        ])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_daily")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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


def craft_root_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Мелкие", callback_data="craft_cat:small:0")],
            [InlineKeyboardButton(text="Средние", callback_data="craft_cat:medium:0")],
            [InlineKeyboardButton(text="Крупные", callback_data="craft_cat:large:0")],
            [InlineKeyboardButton(text="Эпические", callback_data="craft_cat:epic:0")],
            [InlineKeyboardButton(text="Легендарные", callback_data="craft_cat:legendary:0")],
            [InlineKeyboardButton(text="Поиск 🔍", callback_data="craft_search")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")],
        ]
    )


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


def task_search_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ В задачи", callback_data="menu_daily")]
        ]
    )


def reward_search_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ В крафт", callback_data="menu_craft")]
        ]
    )


# =========================
# ВСПОМОГАТЕЛЬНОЕ: список задач / наград с пагинацией
# =========================

async def show_tasks_list(
    callback: CallbackQuery,
    tasks: list[dict],
    base_cb: str,
    title: str,
):
    """Показывает список задач с постраничной навигацией."""
    data = callback.data
    parts = data.split(":")
    page = int(parts[-1]) if len(parts) > 1 and parts[-1].isdigit() else 0

    per_page = 5
    total = len(tasks)
    if total == 0:
        await callback.answer("Пока нет задач в этой группе.", show_alert=True)
        return

    total_pages = (total - 1) // per_page + 1
    page = max(0, min(page, total_pages - 1))

    start = page * per_page
    end = start + per_page
    subset = tasks[start:end]

    kb_rows = []
    for task in subset:
        kb_rows.append([
            InlineKeyboardButton(
                text=task["name"],
                callback_data=f"task_pick:{task['id']}"
            )
        ])

    nav_row = []
    if page > 0:
        nav_row.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=f"{base_cb}:{page-1}"
            )
        )
    if page < total_pages - 1:
        nav_row.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=f"{base_cb}:{page+1}"
            )
        )
    if nav_row:
        kb_rows.append(nav_row)

    kb_rows.append(
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_daily")]
    )

    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)

    text = f"{title}\nСтраница {page+1}/{total_pages}"
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


async def show_rewards_category(
    callback: CallbackQuery,
    category: str,
):
    """Список наград по категории с учётом текущих эмблем."""
    parts = callback.data.split(":")
    page = int(parts[-1]) if parts and parts[-1].isdigit() else 0
    user_id = callback.from_user.id

    rewards = get_rewards_by_category(category)
    per_page = 5
    total = len(rewards)
    if total == 0:
        await callback.answer("Пока нет наград в этой категории.", show_alert=True)
        return

    total_pages = (total - 1) // per_page + 1
    page = max(0, min(page, total_pages - 1))

    start = page * per_page
    end = start + per_page
    subset = rewards[start:end]

    kb_rows = []
    for r in subset:
        cost_parts = []
        for token, need in r["cost"].items():
            cost_parts.append(
                format_token_balance_for_user(user_id, token, need)
            )
        cost_str = " ".join(cost_parts)
        kb_rows.append([
            InlineKeyboardButton(
                text=f"{r['name']} — {cost_str}",
                callback_data=f"craft:{r['id']}",
            )
        ])

    nav_row = []
    if page > 0:
        nav_row.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=f"craft_cat:{category}:{page-1}"
            )
        )
    if page < total_pages - 1:
        nav_row.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=f"craft_cat:{category}:{page+1}"
            )
        )
    if nav_row:
        kb_rows.append(nav_row)

    kb_rows.append(
        [InlineKeyboardButton(text="⬅️ Категории", callback_data="menu_craft")]
    )

    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)

    cat_name = {
        "small": "Мелкие",
        "medium": "Средние",
        "large": "Крупные",
        "epic": "Эпические",
        "legendary": "Легендарные",
    }.get(category, category)

    text = f"Награды: {cat_name}\nСтраница {page+1}/{total_pages}"
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


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


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    await message.answer("Главное меню:", reply_markup=main_menu_kb())


# ---------- MAIN MENU ----------

@router.callback_query(F.data == "back_main")
async def cb_back_main(callback: CallbackQuery):
    await callback.message.edit_text("Главное меню:", reply_markup=main_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "menu_daily")
async def cb_menu_daily(callback: CallbackQuery):
    await callback.message.edit_text("Как выбрать задачу?", reply_markup=daily_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "menu_craft")
async def cb_menu_craft(callback: CallbackQuery):
    await callback.message.edit_text("Крафт наград:", reply_markup=craft_root_kb())
    await callback.answer()


@router.callback_query(F.data == "menu_season")
async def cb_menu_season(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    rp = user["rp"]
    bp = user["bp_level"]
    countdown = get_season_countdown_text()
    text = (
        "🌕 <b>Season of Lunar Archives</b>\n"
        "Тема: фокус, порядок, спокойствие.\n\n"
        f"Уровень: <b>{bp}</b>/50\n"
        f"RP: <b>{rp}</b>\n"
        f"{countdown}"
    )
    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=main_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "bp_rewards")
async def cb_bp_rewards(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    bp = user["bp_level"]

    lines = ["🎁 <b>Награды батл-паса</b>"]
    for lvl in range(1, 51):
        reward = BATTLE_PASS.get(lvl, {})
        if "tokens" in reward:
            parts = []
            for token, amt in reward["tokens"].items():
                emoji = TOKEN_EMOJI.get(token, "🔸")
                if amt > 1:
                    parts.append(f"{emoji}×{amt}")
                else:
                    parts.append(emoji)
            reward_text = "Эмблемы: " + " ".join(parts)
        elif "real" in reward:
            reward_text = "🎁 " + reward["real"]
        else:
            reward_text = "—"

        base = f"Ур. {lvl}: {reward_text} — {RP_PER_LEVEL} RP"

        # зачёркиваем уже полученное
        if lvl <= bp and reward_text != "—":
            line = f"<s>{base}</s>"
        else:
            line = base

        # стрелочка на текущем уровне
        if lvl == bp:
            line = "➡️ " + line

        lines.append(line)

    text = "\n".join(lines)
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
        f"Эмблемы:\n{tokens_text}"
    )

    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=main_menu_kb())
    await callback.answer()


# ---------- DAILY: ВЫБОР СПОСОБА ----------

@router.callback_query(F.data == "daily_by_type")
async def cb_daily_by_type(callback: CallbackQuery):
    await callback.message.edit_text("Выбери сложность:", reply_markup=daily_type_select_kb())
    await callback.answer()


@router.callback_query(F.data == "daily_by_cat")
async def cb_daily_by_cat(callback: CallbackQuery):
    await callback.message.edit_text("Выбери категорию:", reply_markup=categories_kb())
    await callback.answer()


@router.callback_query(F.data == "daily_by_token")
async def cb_daily_by_token(callback: CallbackQuery):
    await callback.message.edit_text("Выбери эмблему:", reply_markup=token_filter_kb())
    await callback.answer()


@router.callback_query(F.data == "daily_search")
async def cb_daily_search(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    user["search_mode"] = "task_search"
    save_users(USERS)

    await callback.message.edit_text(
        "🔍 Введи часть названия задачи (например: «кухню», «прогулка», «mtg»).\n"
        "Я покажу список подходящих задач.",
        reply_markup=task_search_back_kb(),
    )
    await callback.answer()


# ---------- DAILY: СПИСОК ПО СЛОЖНОСТИ ----------

@router.callback_query(F.data.startswith("daily_easy"))
async def cb_daily_easy(callback: CallbackQuery):
    tasks = get_tasks_by_type("easy")
    await show_tasks_list(callback, tasks, "daily_easy", "Лёгкие задачи")


@router.callback_query(F.data.startswith("daily_medium"))
async def cb_daily_medium(callback: CallbackQuery):
    tasks = get_tasks_by_type("medium")
    await show_tasks_list(callback, tasks, "daily_medium", "Средние задачи")


@router.callback_query(F.data.startswith("daily_hard"))
async def cb_daily_hard(callback: CallbackQuery):
    tasks = get_tasks_by_type("hard")
    await show_tasks_list(callback, tasks, "daily_hard", "Сложные задачи")


@router.callback_query(F.data.startswith("daily_epic"))
async def cb_daily_epic(callback: CallbackQuery):
    tasks = get_tasks_by_type("epic")
    await show_tasks_list(callback, tasks, "daily_epic", "Эпические задачи")


# ---------- DAILY: СПИСОК ПО КАТЕГОРИИ ----------

@router.callback_query(F.data.startswith("daily_cat:"))
async def cb_daily_cat(callback: CallbackQuery):
    # format: daily_cat:<category>:<page>
    parts = callback.data.split(":")
    if len(parts) < 2:
        await callback.answer("Ошибка категории.", show_alert=True)
        return
    cat = parts[1]
    if cat not in CATEGORIES:
        await callback.answer("Неизвестная категория.", show_alert=True)
        return

    tasks = get_tasks_by_category(cat)
    base_cb = f"daily_cat:{cat}"
    title = f"Задачи категории: {CATEGORIES[cat]}"
    await show_tasks_list(callback, tasks, base_cb, title)


# ---------- DAILY: СПИСОК ПО ЭМБЛЕМАМ ----------

@router.callback_query(F.data.startswith("daily_token:"))
async def cb_daily_token(callback: CallbackQuery):
    # format: daily_token:<token>:<page>
    parts = callback.data.split(":")
    if len(parts) < 2:
        await callback.answer("Ошибка эмблемы.", show_alert=True)
        return
    token = parts[1]
    emoji = TOKEN_EMOJI.get(token, "🔸")

    tasks = get_tasks_by_token(token)
    base_cb = f"daily_token:{token}"
    title = f"Задачи с эмблемой {emoji}"
    await show_tasks_list(callback, tasks, base_cb, title)


# ---------- DAILY: ВЫБОР КОНКРЕТНОЙ ЗАДАЧИ ----------

@router.callback_query(F.data.startswith("task_pick:"))
async def cb_task_pick(callback: CallbackQuery):
    tid = callback.data.split(":", 1)[1]
    task = get_task_by_id(tid)
    if not task:
        await callback.answer("Задача не найдена.", show_alert=True)
        return

    tokens_str = format_task_tokens_award(task["tokens"])
    text = (
        f"Задача:\n<b>{task['name']}</b>\n\n"
        f"Сложность: {task['type']}\n"
        f"Категория: {CATEGORIES.get(task['category'], task['category'])}\n"
        f"Опыт: {task['rp']} RP\n"
        f"Эмблемы: {tokens_str}"
    )
    await callback.message.edit_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=task_action_kb(task["id"]),
    )
    await callback.answer()


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

    tokens_text = format_task_tokens_award(task["tokens"])
    text = (
        f"✅ Задача выполнена:\n<b>{task['name']}</b>\n\n"
        f"+{task['rp']} RP\n"
        f"Эмблемы: {tokens_text}"
    )
    await callback.message.edit_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=daily_menu_kb(),
    )
    await callback.answer("Готово!")


# ---------- ПОИСК ЗАДАЧ / НАГРАД ПО ТЕКСТУ ----------

@router.message(F.text)
async def handle_text(message: Message):
    user = get_user(message.from_user.id)
    mode = user.get("search_mode")

    # ---- поиск задач ----
    if mode == "task_search":
        query = (message.text or "").strip().lower()
        if not query:
            await message.answer("Введи часть названия задачи, пожалуйста.")
            return

        user["search_mode"] = None
        save_users(USERS)

        results = [
            t for t in TASKS
            if query in t["name"].lower()
        ]

        if not results:
            await message.answer(
                "Ничего не нашлось.\n"
                "Попробуй другое слово или зайди в список задач.",
                reply_markup=task_search_back_kb(),
            )
            return

        results = results[:10]

        kb_rows = [
            [
                InlineKeyboardButton(
                    text=t["name"],
                    callback_data=f"task_pick:{t['id']}"
                )
            ]
            for t in results
        ]
        kb_rows.append(
            [InlineKeyboardButton(text="⬅️ В задачи", callback_data="menu_daily")]
        )

        kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)

        await message.answer(
            "Вот что нашлось:",
            reply_markup=kb,
        )
        return

    # ---- поиск наград ----
    if mode == "reward_search":
        query = (message.text or "").strip().lower()
        if not query:
            await message.answer("Введи часть названия награды, пожалуйста.")
            return

        user["search_mode"] = None
        save_users(USERS)

        results = [
            r for r in REWARDS
            if query in r["name"].lower()
        ]

        if not results:
            await message.answer(
                "Ничего не нашлось.\n"
                "Попробуй другое слово или зайди в крафт.",
                reply_markup=reward_search_back_kb(),
            )
            return

        results = results[:10]
        uid = message.from_user.id

        kb_rows = []
        for r in results:
            cost_parts = []
            for token, need in r["cost"].items():
                cost_parts.append(
                    format_token_balance_for_user(uid, token, need)
                )
            cost_str = " ".join(cost_parts)
            kb_rows.append([
                InlineKeyboardButton(
                    text=f"{r['name']} — {cost_str}",
                    callback_data=f"craft:{r['id']}",
                )
            ])

        kb_rows.append(
            [InlineKeyboardButton(text="⬅️ В крафт", callback_data="menu_craft")]
        )

        kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
        await message.answer(
            "Награды, которые я нашла:",
            reply_markup=kb,
        )
        return

    # если не в режиме поиска — игнорим текст (бот-компаньон, не чат-бот)
    return


# ---------- JOINT TASKS ----------

@router.callback_query(F.data == "joint_easy")
async def cb_joint_easy(callback: CallbackQuery, bot: Bot):
    task = get_task_by_id("joint_tea_10")
    if not task:
        await callback.answer("Нет задачи.", show_alert=True)
        return

    user_id = callback.from_user.id
    add_tokens(user_id, task["tokens"])
    await add_rp_and_check_bp(bot, user_id, task["rp"])

    toks = format_task_tokens_award(task["tokens"])
    text = (
        f"💞 Совместный лёгкий квест:\n<b>{task['name']}</b>\n\n"
        f"+{task['rp']} RP\nЭмблемы: {toks}"
    )

    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=joint_menu_kb())
    await callback.answer("Совместный момент засчитан 💞")


@router.callback_query(F.data == "joint_cozy")
async def cb_joint_cozy(callback: CallbackQuery, bot: Bot):
    task = get_task_by_id("joint_cozy_evening")
    if not task:
        await callback.answer("Нет задачи.", show_alert=True)
        return

    user_id = callback.from_user.id
    add_tokens(user_id, task["tokens"])
    await add_rp_and_check_bp(bot, user_id, task["rp"])

    toks = format_task_tokens_award(task["tokens"])
    text = (
        f"💞 Уютный вечер-квест:\n<b>{task['name']}</b>\n\n"
        f"+{task['rp']} RP\nЭмблемы: {toks}"
    )

    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=joint_menu_kb())
    await callback.answer("Записано ✨")


# ---------- MTG TASKS (быстрые кнопки) ----------

@router.callback_query(F.data == "mtg_small")
async def cb_mtg_small(callback: CallbackQuery, bot: Bot):
    task = get_task_by_id("mtg_sort_20")
    if not task:
        await callback.answer("Нет задачи.", show_alert=True)
        return

    user_id = callback.from_user.id
    add_tokens(user_id, task["tokens"])
    await add_rp_and_check_bp(bot, user_id, task["rp"])

    toks = format_task_tokens_award(task["tokens"])
    text = (
        f"🃏 MTG-квест:\n<b>{task['name']}</b>\n\n"
        f"+{task['rp']} RP\nЭмблемы: {toks}"
    )

    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=mtg_menu_kb())
    await callback.answer("Карты стали ещё аккуратнее 🃏")


@router.callback_query(F.data == "mtg_org")
async def cb_mtg_org(callback: CallbackQuery, bot: Bot):
    task = get_task_by_id("mtg_box_organize")
    if not task:
        await callback.answer("Нет задачи.", show_alert=True)
        return

    user_id = callback.from_user.id
    add_tokens(user_id, task["tokens"])
    await add_rp_and_check_bp(bot, user_id, task["rp"])

    toks = format_task_tokens_award(task["tokens"])
    text = (
        f"🃏 MTG-организация:\n<b>{task['name']}</b>\n\n"
        f"+{task['rp']} RP\nЭмблемы: {toks}"
    )

    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=mtg_menu_kb())
    await callback.answer("MTG-порядок становится сильнее ✨")


# ---------- CRAFT ----------

@router.callback_query(F.data.startswith("craft_cat:"))
async def cb_craft_cat(callback: CallbackQuery):
    # craft_cat:<category>:<page>
    parts = callback.data.split(":")
    if len(parts) < 2:
        await callback.answer("Ошибка категории.", show_alert=True)
        return
    cat = parts[1]
    await show_rewards_category(callback, cat)


@router.callback_query(F.data == "craft_search")
async def cb_craft_search(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    user["search_mode"] = "reward_search"
    save_users(USERS)

    await callback.message.edit_text(
        "🔍 Введи часть названия награды.\n"
        "Например: «mtg», «игра», «техника», «доставка».",
        reply_markup=reward_search_back_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("craft:"))
async def cb_craft(callback: CallbackQuery, bot: Bot):
    rid = callback.data.split(":", 1)[1]
    reward = get_reward_by_id(rid)
    if not reward:
        await callback.answer("Награда не найдена.", show_alert=True)
        return

    user_id = callback.from_user.id
    if not user_can_afford(user_id, reward):
        await callback.answer("Не хватает эмблем для этой награды.", show_alert=True)
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

    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=craft_root_kb())
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
