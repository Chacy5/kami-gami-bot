
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

ALL_EMBLEMS = sorted({
    emb
    for entry in TASKS
    for emb in entry.get("emblems", {}).keys()
} | {
    emb
    for reward in REWARDS
    for emb in reward.get("cost", {}).keys()
})

TASK_ICON_BY_CATEGORY = {
    "selfcare": "💆",
    "cleaning": "🧹",
    "dog": "🐕",
    "finance": "💰",
    "admin": "📋",
    "work": "💻",
    "together": "🤝",
    "hobby": "🎲",
    "mixed": "🌀",
    "home": "🏠",
    "errands": "🛒",
    "mtg": "🃏",
    "music": "🎵",
    "cooking": "🍳",
}

TASK_ICON_BY_DIFFICULTY = {
    "easy": "🟢",
    "normal": "🟡",
    "hard": "🔴",
}

DIFFICULTY_ORDER = {"easy": 0, "normal": 1, "hard": 2}

TASK_REWARD_EMBLEMS = sorted({
    emb
    for entry in TASKS
    for emb in (entry.get("reward_emblems") or entry.get("emblems") or {}).keys()
})

DEFAULT_TASK_FILTERS = {
    "category": None,
    "query": None,
    "sort": "id",  # id | difficulty
    "emblem": None,
}

DEFAULT_REWARD_FILTERS = {
    "category": None,
    "query": None,
    "affordable_only": False,
    "sort": "id",  # id | cost
}

USERS: Dict[int, Dict] = {}

CURRENT_SEASON = 1
SEASON_DURATION_DAYS = 28
SEASON_START_DATE = datetime.utcnow()
SEASON_END_DATE = SEASON_START_DATE + timedelta(days=SEASON_DURATION_DAYS)

MAX_LVL = 50
BASE_XP = 50        # первый уровень
GROWTH = 1.03       # рост сложности 3% — идеально на сезон ~27 дней

def get_task_icon(task: Dict) -> str:
    return TASK_ICON_BY_CATEGORY.get(
        task.get("category"),
        TASK_ICON_BY_DIFFICULTY.get(task.get("difficulty"), "🗒️"),
    )

def task_reward_emblems(task: Dict) -> Dict[str, int]:
    return task.get("reward_emblems") or task.get("emblems") or {}

def task_reward_exp(task: Dict) -> int:
    return task.get("reward_exp") or task.get("xp") or 0

def format_emblems(emblems: Dict[str, int]) -> str:
    return ", ".join(f"{emb} × {amt}" for emb, amt in emblems.items())

def xp_for_level(level: int) -> int:
    """XP для перехода с этого уровня на следующий."""
    return int(BASE_XP * (GROWTH ** (level - 1)))

def total_xp_for_level(level: int) -> int:
    """Сколько XP нужно всего до конца указанного уровня."""
    if level <= 0:
        return 0
    return sum(xp_for_level(i) for i in range(1, level + 1))

def get_bp_progress(user: Dict) -> str:
    lvl = user["bp_level"]
    exp = user["exp"]

    if lvl >= MAX_LVL:
        return f"Боевой пропуск: уровень {MAX_LVL} (максимум)."

    current_total = total_xp_for_level(lvl - 1)
    next_total = total_xp_for_level(lvl)

    in_level = exp - current_total
    need_in_level = next_total - current_total

    return f"Боевой пропуск: уровень {lvl} — {in_level}/{need_in_level} XP до следующего уровня."

def get_task_filters(user: Dict) -> Dict:
    if "task_filters" not in user:
        user["task_filters"] = DEFAULT_TASK_FILTERS.copy()
    return user["task_filters"]

def get_reward_filters(user: Dict) -> Dict:
    if "reward_filters" not in user:
        user["reward_filters"] = DEFAULT_REWARD_FILTERS.copy()
    return user["reward_filters"]

def get_user(user_id: int) -> Dict:
    if user_id not in USERS:
        USERS[user_id] = {
            "id": user_id,
            "emblems": {emb: 0 for emb in ALL_EMBLEMS},
            "exp": 0,
            "bp_level": 1,
            "bp_exp_to_next": 50,
            "completed_tasks": [],
            "pinned_tasks": [],
            "version": 2,
            "task_filters": DEFAULT_TASK_FILTERS.copy(),
            "reward_filters": DEFAULT_REWARD_FILTERS.copy(),
        }
    return USERS[user_id]

MAX_LVL = 50
BASE_XP = 50        # первый уровень
GROWTH = 1.03       # рост сложности 3% — идеально на сезон 27 дней

def xp_for_level(level: int) -> int:
    """XP для перехода С ЭТОГО уровня на следующий"""
    return int(BASE_XP * (GROWTH ** (level - 1)))

def total_xp_for_level(level: int) -> int:
    """Сколько XP нужно всего до конца уровня"""
    if level <= 0:
        return 0
    return sum(xp_for_level(i) for i in range(1, level + 1))

def get_bp_progress(user: Dict) -> str:
    lvl = user["bp_level"]
    exp = user["exp"]

    if lvl >= MAX_LVL:
        return f"Боевой пропуск: уровень {MAX_LVL} (максимум)."

    current_total = total_xp_for_level(lvl - 1)
    next_total = total_xp_for_level(lvl)

    in_level = exp - current_total
    need_in_level = next_total - current_total

    return f"Боевой пропуск: уровень {lvl} — {in_level}/{need_in_level} XP до следующего уровня."


def add_exp(user: Dict, amount: int) -> List[Dict]:
    rewards = []
    user["exp"] += amount
    while user["bp_level"] < MAX_LVL:
        next_level_total = total_xp_for_level(user["bp_level"])
        if user["exp"] < next_level_total:
            break
        user["bp_level"] += 1
        for r in BP_REWARDS:
            if r["level"] == user["bp_level"]:
                rewards.append(r)
                for emb, amt in r.get("emblems", {}).items():
                    user["emblems"][emb] = user["emblems"].get(emb, 0) + amt
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

def summarize_task_filters(filters: Dict) -> str:
    parts = []
    if filters.get("category"):
        parts.append(f"категория: {filters['category']}")
    if filters.get("query"):
        parts.append(f"поиск: «{filters['query']}»")
    parts.append(f"сортировка: {'сложность' if filters.get('sort') == 'difficulty' else 'id'}")
    parts.append(f"эмблема: {filters.get('emblem') or 'все'}")
    return "; ".join(parts)

def filtered_tasks(user: Dict) -> List[Dict]:
    filters = get_task_filters(user)
    items = TASKS
    if filters.get("category"):
        items = [t for t in items if t["category"] == filters["category"]]
    if filters.get("query"):
        q = filters["query"].lower()
        items = [t for t in items if q in t["name"].lower() or q in t.get("description", "").lower()]
    if filters.get("emblem"):
        needed = filters["emblem"]
        items = [t for t in items if needed in task_reward_emblems(t)]
    if filters.get("sort") == "difficulty":
        items = sorted(items, key=lambda t: (DIFFICULTY_ORDER.get(t.get("difficulty"), 99), t["id"]))
    else:
        items = sorted(items, key=lambda t: t["id"])
    return items

def build_tasks_list(user: Dict) -> tuple[str, InlineKeyboardMarkup]:
    filters = get_task_filters(user)
    tasks_list = filtered_tasks(user)
    kb = InlineKeyboardBuilder()
    for t in tasks_list:
        kb.button(text=f"{get_task_icon(t)} {t['name']}", callback_data=f"task_view_{t['id']}")
    kb.button(
        text=f"↕️ Сортировка: {'сложность' if filters.get('sort') == 'difficulty' else 'id'}",
        callback_data="tasks_toggle_sort",
    )
    kb.button(
        text=f"🎯 Эмблема: {filters.get('emblem') or 'все'}",
        callback_data="tasks_filter_emblem_menu",
    )
    kb.button(text="♻️ Сбросить фильтры", callback_data="tasks_filters_reset")
    kb.button(text="⬅️ Категории", callback_data="menu_tasks")
    kb.adjust(1)
    text_lines = [
        "📜 Задания",
        summarize_task_filters(filters),
        "",
        "Выбери задание из списка:",
    ]
    return "\n".join(text_lines), kb.as_markup()

def build_task_emblem_filter_kb(current: Optional[str]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for emb in TASK_REWARD_EMBLEMS:
        marker = "✓" if emb == current else " "
        kb.button(text=f"{marker} {emb}", callback_data=f"tasks_set_emblem_{emb}")
    kb.button(text="Показать все", callback_data="tasks_set_emblem_clear")
    kb.button(text="⬅️ Назад к заданиям", callback_data="tasks_back_to_list")
    kb.adjust(2)
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

def summarize_reward_filters(filters: Dict) -> str:
    parts = []
    if filters.get("category"):
        parts.append(f"категория: {filters['category']}")
    if filters.get("query"):
        parts.append(f"поиск: «{filters['query']}»")
    parts.append(f"доступные: {'да' if filters.get('affordable_only') else 'нет'}")
    parts.append(f"сортировка: {'стоимость' if filters.get('sort') == 'cost' else 'id'}")
    return "; ".join(parts)

def filtered_rewards(user: Dict) -> List[Dict]:
    filters = get_reward_filters(user)
    items = REWARDS
    if filters.get("category"):
        items = [r for r in items if r["category"] == filters["category"]]
    if filters.get("query"):
        q = filters["query"].lower()
        items = [r for r in items if q in r["name"].lower() or q in r.get("description", "").lower()]
    if filters.get("affordable_only"):
        def affordable(reward):
            for emb, need in reward["cost"].items():
                if user["emblems"].get(emb, 0) < need:
                    return False
            return True
        items = [r for r in items if affordable(r)]
    if filters.get("sort") == "cost":
        items = sorted(items, key=lambda r: sum(r["cost"].values()))
    else:
        items = sorted(items, key=lambda r: r["id"])
    return items

def build_rewards_list(user: Dict) -> tuple[str, InlineKeyboardMarkup]:
    filters = get_reward_filters(user)
    rewards_list = filtered_rewards(user)
    kb = InlineKeyboardBuilder()
    for r in rewards_list:
        kb.button(text=f"{r['emoji']} {r['name']}", callback_data=f"reward_{r['id']}")
    kb.button(
        text=f"✅ Доступные: {'вкл' if filters.get('affordable_only') else 'выкл'}",
        callback_data="shop_toggle_affordable",
    )
    kb.button(
        text=f"↕️ Сортировка: {'эмблемы' if filters.get('sort') == 'cost' else 'id'}",
        callback_data="shop_toggle_sort",
    )
    kb.button(text="♻️ Сбросить фильтры", callback_data="shop_filters_reset")
    kb.button(text="⬅️ Категории", callback_data="menu_shop")
    kb.adjust(1)
    text_lines = [
        "🏆 Магазин наград",
        summarize_reward_filters(filters),
        "",
        "Выбери награду из списка:",
    ]
    return "\n".join(text_lines), kb.as_markup()

def build_bp_rewards_view(user: Dict) -> str:
    lines = [f"🎫 Боевой пропуск — сезон {CURRENT_SEASON}", season_time_left(), ""]
    lvl = user["bp_level"]
    exp = user["exp"]
    current_total = total_xp_for_level(lvl - 1)
    next_total = total_xp_for_level(lvl)
    need_in_level = next_total - current_total
    current_in_level = exp - current_total if lvl < MAX_LVL else need_in_level
    remaining_in_level = max(need_in_level - current_in_level, 0) if lvl < MAX_LVL else 0
    if lvl >= MAX_LVL:
        lines.append("Уровень 50 • максимум.")
    else:
        filled = int((current_in_level / need_in_level) * 12) if need_in_level else 12
        bar = "█" * min(filled, 12) + "░" * (12 - min(filled, 12))
        lines.append(f"Уровень {lvl} • {current_in_level}/{need_in_level} XP до следующего")
        lines.append(f"[{bar}] осталось {remaining_in_level} XP")
    lines.append("")
    lines.append("Награды:")
    for entry in BP_REWARDS:
        entry_lvl = entry["level"]
        reward_name = entry["name"]
        reward_desc = entry.get("description", "")
        emblem_text = format_emblems(entry.get("emblems", {}))
        total_for_level = total_xp_for_level(entry_lvl)
        need = max(total_for_level - exp, 0)
        status = "✅" if entry_lvl <= lvl else "⏳" if entry_lvl == lvl + 1 else "·"
        main = f"{status} {entry_lvl:>2} • {reward_name}"
        if status != "✅":
            main += f" — ещё {need} XP"
        lines.append(main)
        detail_parts = []
        if reward_desc:
            detail_parts.append(reward_desc)
        if emblem_text:
            detail_parts.append(f"Эмблемы: {emblem_text}")
        if detail_parts:
            lines.append("    " + " | ".join(detail_parts))
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
    user = get_user(callback.from_user.id)
    cat = callback.data.removeprefix("tasks_cat_")
    filters = get_task_filters(user)
    filters["category"] = None if cat == "all" else cat
    text, kb = build_tasks_list(user)
    await callback.message.edit_text(text, reply_markup=kb)
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

@router.callback_query(F.data == "tasks_toggle_sort")
async def cb_tasks_toggle_sort(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    filters = get_task_filters(user)
    filters["sort"] = "difficulty" if filters.get("sort") != "difficulty" else "id"
    text, kb = build_tasks_list(user)
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer("Сортировка обновлена.")

@router.callback_query(F.data == "tasks_filters_reset")
async def cb_tasks_filters_reset(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    user["task_filters"] = DEFAULT_TASK_FILTERS.copy()
    text, kb = build_tasks_list(user)
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer("Фильтры сброшены.")

@router.callback_query(F.data == "tasks_filter_emblem_menu")
async def cb_tasks_filter_emblem_menu(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    current = get_task_filters(user).get("emblem")
    kb = build_task_emblem_filter_kb(current)
    await callback.message.edit_text(
        "🎯 Фильтр по эмблемам.\nВыбери эмблему, чтобы оставить задания с этой наградой.",
        reply_markup=kb
    )
    await callback.answer()

@router.callback_query(F.data == "tasks_set_emblem_clear")
async def cb_tasks_set_emblem_clear(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    get_task_filters(user)["emblem"] = None
    text, kb = build_tasks_list(user)
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer("Фильтр снят.")

@router.callback_query(F.data.startswith("tasks_set_emblem_"))
async def cb_tasks_set_emblem(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    emb = callback.data.removeprefix("tasks_set_emblem_")
    get_task_filters(user)["emblem"] = emb
    text, kb = build_tasks_list(user)
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer(f"Эмблема {emb}")

@router.callback_query(F.data == "tasks_back_to_list")
async def cb_tasks_back_to_list(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    text, kb = build_tasks_list(user)
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@router.message()
async def any_text(message: Message):
    user = get_user(message.from_user.id)
    if user.get("awaiting_task_search"):
        query = message.text.strip()
        user["awaiting_task_search"] = False
        get_task_filters(user)["query"] = query
        text, kb = build_tasks_list(user)
        await message.answer(text, reply_markup=kb)
        return
    if user.get("awaiting_shop_search"):
        query = message.text.strip()
        user["awaiting_shop_search"] = False
        get_reward_filters(user)["query"] = query
        text, kb = build_rewards_list(user)
        await message.answer(text, reply_markup=kb)
        return
    await message.answer(
        "Я пока понимаю только команды меню.\n"
        "Используй кнопки ниже.",
        reply_markup=build_main_menu()
    )

@router.callback_query(F.data.startswith("task_view_"))
async def cb_task_detail(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    tid = int(callback.data.removeprefix("task_view_"))
    task = next((t for t in TASKS if t["id"] == tid), None)
    if not task:
        await callback.answer("Задание не найдено.", show_alert=True)
        return
    emblems_reward = task_reward_emblems(task)
    exp_reward = task_reward_exp(task)
    text = (
        f"{get_task_icon(task)} <b>{task['name']}</b>\n\n"
        f"{task.get('description', '')}\n\n"
        f"Эмблемы за выполнение:\n"
    )
    for emb, amt in emblems_reward.items():
        text += f"• {emb} × {amt}\n"
    text += f"\nОпыт: +{exp_reward} XP"
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
    emblems_reward = task_reward_emblems(task)
    exp_reward = task_reward_exp(task)
    for emb, amt in emblems_reward.items():
        user["emblems"][emb] = user["emblems"].get(emb, 0) + amt
    level_rewards = add_exp(user, exp_reward)
    text = (
        f"✅ Задание выполнено: <b>{task['name']}</b>\n\n"
        "Ты получил:\n"
    )
    for emb, amt in emblems_reward.items():
        text += f"• {emb} × {amt}\n"
    text += f"\nОпыт: +{exp_reward} XP\n"
    if level_rewards:
        text += "\n🎉 Повышение уровня боевого пропуска!\n"
        for r in level_rewards:
            parts = [r["name"]]
            if r.get("description"):
                parts.append(r["description"])
            emblem_bonus = format_emblems(r.get("emblems", {}))
            if emblem_bonus:
                parts.append(f"Эмблемы: {emblem_bonus}")
            text += f"• Уровень {r['level']}: " + " — ".join(parts) + "\n"
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
    user = get_user(callback.from_user.id)
    cat = callback.data.removeprefix("shop_cat_")
    filters = get_reward_filters(user)
    filters["category"] = None if cat == "all" else cat
    text, kb = build_rewards_list(user)
    await callback.message.edit_text(text, reply_markup=kb)
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

@router.callback_query(F.data == "shop_toggle_affordable")
async def cb_shop_toggle_affordable(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    filters = get_reward_filters(user)
    filters["affordable_only"] = not filters.get("affordable_only")
    text, kb = build_rewards_list(user)
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer("Фильтр доступных обновлён.")

@router.callback_query(F.data == "shop_toggle_sort")
async def cb_shop_toggle_sort(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    filters = get_reward_filters(user)
    filters["sort"] = "cost" if filters.get("sort") != "cost" else "id"
    text, kb = build_rewards_list(user)
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer("Сортировка обновлена.")

@router.callback_query(F.data == "shop_filters_reset")
async def cb_shop_filters_reset(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    user["reward_filters"] = DEFAULT_REWARD_FILTERS.copy()
    text, kb = build_rewards_list(user)
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer("Фильтры сброшены.")

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
