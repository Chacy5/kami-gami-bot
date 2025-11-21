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


def get_tasks_by_type(task_type: str):
    return [t for t in TASKS if t["type"] == task_type]


def get_random_task(task_type: str):
    candidates = get_tasks_by_type(task_type)
    return random.choice(candidates) if candidates else None


# =========================
# КРАФТ НАГРАД — расширенный
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
        "name": "Крупная техника (до ~150₾)",
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
    task = get_task_by_id("joint_tea_10")
    if not task:
        await callback.answer("Нет задачи.", show_alert=True)
        return

    user_id = callback.from_user.id
    add_tokens(user_id, task["tokens"])
    await add_rp_and_check_bp(bot, user_id, task["rp"])

    toks = ", ".join(task["tokens"])
    text = (
        f"💞 Совместный лёгкий квест:\n<b>{task['name']}</b>\n\n"
        f"+{task['rp']} RP\nЖетоны: {toks}"
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
    task = get_task_by_id("mtg_sort_20")
    if not task:
        await callback.answer("Нет задачи.", show_alert=True)
        return

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
    task = get_task_by_id("mtg_box_organize")
    if not task:
        await callback.answer("Нет задачи.", show_alert=True)
        return

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
