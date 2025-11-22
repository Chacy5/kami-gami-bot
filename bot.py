
import os
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from aiogram import Bot, Dispatcher, Router, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from rewards import REWARDS, BP_REWARDS
from tasks import TASKS

BOT_TOKEN = os.getenv("BOT_TOKEN", "PASTE_YOUR_TOKEN_HERE")

router = Router()

USERS: Dict[int, Dict] = {}

CURRENT_SEASON = 1
SEASON_DURATION_DAYS = 28
SEASON_START_DATE = datetime.utcnow()
SEASON_END_DATE = SEASON_START_DATE + timedelta(days=SEASON_DURATION_DAYS)

def get_user(user_id: int) -> Dict:
    if user_id not in USERS:
        USERS[user_id] = {
            "id": user_id,
            "emblems": {emb: 0 for emb in [
                "𓂀", "✶", "℘", "✦", "☾",
                "✺", "♖", "✣", "𓍝", "✧",
                "⚑", "✥", "✢", "♆", "✺",
                "⚙", "♜", "✶", "♧", "✹"
            ]},
            "exp": 0,
            "bp_level": 1,
            "bp_exp_to_next": 50,
            "completed_tasks": [],
            "pinned_tasks": [],
            "version": 2,
        }
    return USERS[user_id]

def get_bp_progress(user: Dict) -> str:
    lvl = user["bp_level"]
    exp = user["exp"]
    per_level = 50
    next_level_exp = lvl * per_level
    current_level_exp = (lvl - 1) * per_level
    in_level = exp - current_level_exp
    need_in_level = next_level_exp - current_level_exp
    if lvl >= 50:
        return "Боевой пропуск: уровень 50 (максимум)."
    return f"Боевой пропуск: уровень {lvl} — {in_level}/{need_in_level} XP до следующего уровня."

def add_exp(user: Dict, amount: int) -> List[Dict]:
    rewards = []
    user["exp"] += amount
    per_level = 50
    while user["bp_level"] < 50:
        next_level_total = user["bp_level"] * per_level
        if user["exp"] >= next_level_total:
            user["bp_level"] += 1
            for r in BP_REWARDS:
                if r["level"] == user["bp_level"]:
                    rewards.append(r)
        else:
            break
    return rewards

def season_time_left() -> str:
    now = datetime.utcnow()
    if now >= SEASON_END_DATE:
        return "Сезон завершён."
    delta = SEASON_END_DATE - now
    days = delta.days
    weeks = days // 7
    rem_days = days % 7
    parts = []
    if weeks > 0:
        parts.append(f"{weeks} нед.")
    if rem_days > 0:
        parts.append(f"{rem_days} дн.")
    if not parts:
        parts.append("меньше суток")
    return "До конца сезона: " + " ".join(parts)

def build_main_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📜 Задания", callback_data="menu_tasks")
    kb.button(text="🏆 Магазин наград", callback_data="menu_shop")
    kb.button(text="🎫 Боевой пропуск", callback_data="menu_bp")
    kb.button(text="🎖 Мои эмблемы", callback_data="menu_emblems")
    kb.adjust(2, 2)
    return kb.as_markup()

def build_task_categories_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Все задания", callback_data="tasks_cat_all")
    used_cats = sorted(set(t["category"] for t in TASKS))
    for c in used_cats:
        kb.button(text=c, callback_data=f"tasks_cat_{c}")
    kb.adjust(2)
    kb.button(text="🔍 Поиск", callback_data="tasks_search")
    kb.button(text="⬅️ Назад", callback_data="back_main")
    kb.adjust(2)
    return kb.as_markup()

def build_tasks_list_kb(category: Optional[str] = None, query: Optional[str] = None) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    filtered = TASKS
    if category and category != "all":
        filtered = [t for t in TASKS if t["category"] == category]
    if query:
        q = query.lower()
        filtered = [t for t in filtered if q in t["name"].lower() or q in t.get("description", "").lower()]
    for t in filtered:
        kb.button(text=f"{t['emoji']} {t['name']}", callback_data=f"task_{t['id']}")
    kb.button(text="⬅️ Категории", callback_data="menu_tasks")
    kb.adjust(1)
    return kb.as_markup()

def build_shop_categories_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Все награды", callback_data="shop_cat_all")
    cats = sorted(set(r["category"] for r in REWARDS))
    for c in cats:
        kb.button(text=c, callback_data=f"shop_cat_{c}")
    kb.button(text="🔍 Поиск", callback_data="shop_search")
    kb.button(text="⬅️ Назад", callback_data="back_main")
    kb.adjust(2)
    return kb.as_markup()

def build_rewards_list_kb(category: Optional[str] = None, query: Optional[str] = None) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    filtered = REWARDS
    if category and category != "all":
        filtered = [r for r in REWARDS if r["category"] == category]
    if query:
        q = query.lower()
        filtered = [r for r in filtered if q in r["name"].lower() or q in r.get("description", "").lower()]
    for r in filtered:
        kb.button(text=f"{r['emoji']} {r['name']}", callback_data=f"reward_{r['id']}")
    kb.button(text="⬅️ Категории", callback_data="menu_shop")
    kb.adjust(1)
    return kb.as_markup()

def build_bp_rewards_view(user: Dict) -> str:
    lines = [f"🎫 Боевой пропуск — сезон {CURRENT_SEASON}", season_time_left(), ""]
    lines.append(get_bp_progress(user))
    lines.append("")
    per_level = 50
    for entry in BP_REWARDS:
        lvl = entry["level"]
        reward_name = entry["name"]
        reward_desc = entry.get("description", "")
        total_for_level = lvl * per_level
        need = total_for_level - user["exp"]
        if need < 0:
            need = 0
        mark = "✓" if lvl <= user["bp_level"] else "➤" if lvl == user["bp_level"] else "·"
        lines.append(f"{mark} Уровень {lvl}: {reward_name} — {reward_desc} (нужно ещё {need} XP)")
    return "\n".join(lines)

def format_emblem_cost(user: Dict, cost: Dict[str, int]) -> str:
    parts = []
    for emb, need in cost.items():
        have = user["emblems"].get(emb, 0)
        color = "🟢" if have >= need else "⚪"
        parts.append(f"{color} {emb} {have}/{need}")
    return "\n".join(parts) if parts else "—"

@router.message(CommandStart())
async def cmd_start(message: Message):
    user = get_user(message.from_user.id)
    text = (
        "Привет! Это твой личный мотивационный ивент.\n\n"
        "• Выполняй задания.\n"
        "• Получай эмблемы и опыт.\n"
        "• Трать эмблемы в магазине наград.\n"
        "• Качай боевой пропуск сезона.\n\n"
        f"{season_time_left()}"
    )
    await message.answer(text, reply_markup=build_main_menu())

@router.callback_query(F.data == "back_main")
async def cb_back_main(callback: CallbackQuery):
    await callback.message.edit_text(
        f"Главное меню.\n{season_time_left()}",
        reply_markup=build_main_menu()
    )
    await callback.answer()

@router.callback_query(F.data == "menu_tasks")
async def cb_menu_tasks(callback: CallbackQuery):
    await callback.message.edit_text(
        "📜 Задания.\nВыбери категорию или поиск.",
        reply_markup=build_task_categories_kb()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("tasks_cat_"))
async def cb_tasks_cat(callback: CallbackQuery):
    cat = callback.data.removeprefix("tasks_cat_")
    if cat == "all":
        cat = None
    kb = build_tasks_list_kb(category=cat)
    await callback.message.edit_text(
        "Выбери задание из списка:",
        reply_markup=kb
    )
    await callback.answer()

@router.callback_query(F.data == "tasks_search")
async def cb_tasks_search(callback: CallbackQuery):
    await callback.message.edit_text(
        "🔍 Введи текст для поиска по заданиям (название или описание).\n\n"
        "Пока просто отправь мне сообщение — я отфильтрую список.",
    )
    user = get_user(callback.from_user.id)
    user["awaiting_task_search"] = True
    await callback.answer()

@router.message()
async def any_text(message: Message):
    user = get_user(message.from_user.id)
    if user.get("awaiting_task_search"):
        query = message.text.strip()
        user["awaiting_task_search"] = False
        kb = build_tasks_list_kb(query=query)
        await message.answer(
            f"Результаты поиска по заданиям для: <b>{query}</b>",
            reply_markup=kb
        )
        return
    if user.get("awaiting_shop_search"):
        query = message.text.strip()
        user["awaiting_shop_search"] = False
        kb = build_rewards_list_kb(query=query)
        await message.answer(
            f"Результаты поиска по наградам для: <b>{query}</b>",
            reply_markup=kb
        )
        return
    await message.answer(
        "Я пока понимаю только команды меню.\n"
        "Используй кнопки ниже.",
        reply_markup=build_main_menu()
    )

@router.callback_query(F.data.startswith("task_"))
async def cb_task_detail(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    tid = int(callback.data.removeprefix("task_"))
    task = next((t for t in TASKS if t["id"] == tid), None)
    if not task:
        await callback.answer("Задание не найдено.", show_alert=True)
        return
    text = (
        f"{task['emoji']} <b>{task['name']}</b>\n\n"
        f"{task.get('description', '')}\n\n"
        f"Эмблемы за выполнение:\n"
    )
    for emb, amt in task["reward_emblems"].items():
        text += f"• {emb} × {amt}\n"
    text += f"\nОпыт: +{task['reward_exp']} XP"
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Отметить выполненным", callback_data=f"task_done_{tid}")
    kb.button(text="⬅️ К заданиям", callback_data="menu_tasks")
    kb.adjust(1)
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()

@router.callback_query(F.data.startswith("task_done_"))
async def cb_task_done(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    tid = int(callback.data.removeprefix("task_done_"))
    task = next((t for t in TASKS if t["id"] == tid), None)
    if not task:
        await callback.answer("Задание не найдено.", show_alert=True)
        return
    for emb, amt in task["reward_emblems"].items():
        user["emblems"][emb] = user["emblems"].get(emb, 0) + amt
    level_rewards = add_exp(user, task["reward_exp"])
    text = (
        f"✅ Задание выполнено: <b>{task['name']}</b>\n\n"
        "Ты получил:\n"
    )
    for emb, amt in task["reward_emblems"].items():
        text += f"• {emb} × {amt}\n"
    text += f"\nОпыт: +{task['reward_exp']} XP\n"
    if level_rewards:
        text += "\n🎉 Повышение уровня боевого пропуска!\n"
        for r in level_rewards:
            text += f"• Уровень {r['level']}: {r['name']}\n"
    text += f"\n{get_bp_progress(user)}"
    await callback.message.edit_text(text, reply_markup=build_main_menu())
    await callback.answer()

@router.callback_query(F.data == "menu_shop")
async def cb_menu_shop(callback: CallbackQuery):
    await callback.message.edit_text(
        "🏆 Магазин наград.\nВыбери категорию или поиск.",
        reply_markup=build_shop_categories_kb()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("shop_cat_"))
async def cb_shop_cat(callback: CallbackQuery):
    cat = callback.data.removeprefix("shop_cat_")
    if cat == "all":
        cat = None
    kb = build_rewards_list_kb(category=cat)
    await callback.message.edit_text(
        "Выбери награду из списка:",
        reply_markup=kb
    )
    await callback.answer()

@router.callback_query(F.data == "shop_search")
async def cb_shop_search(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    user["awaiting_shop_search"] = True
    await callback.message.edit_text(
        "🔍 Введи текст для поиска по наградам (название или описание).\n\n"
        "Просто отправь мне сообщение.",
    )
    await callback.answer()

@router.callback_query(F.data.startswith("reward_"))
async def cb_reward_detail(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    rid = int(callback.data.removeprefix("reward_"))
    reward = next((r for r in REWARDS if r["id"] == rid), None)
    if not reward:
        await callback.answer("Награда не найдена.", show_alert=True)
        return
    text = (
        f"{reward['emoji']} <b>{reward['name']}</b>\n\n"
        f"{reward.get('description', '')}\n\n"
        "Стоимость (эмблемы):\n"
        f"{format_emblem_cost(user, reward['cost'])}"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="🎁 Получить награду", callback_data=f"reward_buy_{rid}")
    kb.button(text="⬅️ К наградам", callback_data="menu_shop")
    kb.adjust(1)
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()

@router.callback_query(F.data.startswith("reward_buy_"))
async def cb_reward_buy(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    rid = int(callback.data.removeprefix("reward_buy_"))
    reward = next((r for r in REWARDS if r["id"] == rid), None)
    if not reward:
        await callback.answer("Награда не найдена.", show_alert=True)
        return
    for emb, need in reward["cost"].items():
        have = user["emblems"].get(emb, 0)
        if have < need:
            await callback.answer("Недостаточно эмблем для этой награды.", show_alert=True)
            return
    for emb, need in reward["cost"].items():
        user["emblems"][emb] -= need
    text = (
        f"🎁 Ты активировал награду: <b>{reward['name']}</b>\n\n"
        f"{reward.get('description', '')}\n\n"
        "Эмблемы списаны.\n"
        "Если награда физическая — Ви получит уведомление и выполнит её в реальном мире. ❤️"
    )
    await callback.message.edit_text(text, reply_markup=build_main_menu())
    await callback.answer()

@router.callback_query(F.data == "menu_bp")
async def cb_menu_bp(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    text = build_bp_rewards_view(user)
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="back_main")
    kb.adjust(1)
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()

@router.callback_query(F.data == "menu_emblems")
async def cb_menu_emblems(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    lines = ["🎖 Твои эмблемы:", ""]
    for emb, val in user["emblems"].items():
        lines.append(f"{emb} → {val}")
    lines.append("")
    lines.append(get_bp_progress(user))
    lines.append(season_time_left())
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="back_main")
    kb.adjust(1)
    await callback.message.edit_text("\n".join(lines), reply_markup=kb.as_markup())
    await callback.answer()

@router.message(Command("status"))
async def cmd_status(message: Message):
    user = get_user(message.from_user.id)
    text = (
        "Твой статус:\n\n"
        f"{get_bp_progress(user)}\n"
        f"{season_time_left()}\n\n"
        "Эмблемы:\n"
    )
    for emb, val in user["emblems"].items():
        text += f"{emb}: {val}\n"
    await message.answer(text)

async def main():
    bot = Bot(
        BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()
    dp.include_router(router)
    print("Bot started...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
