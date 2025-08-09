
# main.py
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import json
import random
import string
from datetime import datetime, timedelta
import calendar

# Configure logging
logging.basicConfig(level=logging.INFO)

# Bot configuration
BOT_TOKEN = "8067408775:AAG9JhYg4F65heKU7CxIbFS-09F5l5cMvkk"  # Replace with your bot token
OWNER_ID = 7377694590  # Replace with owner's Telegram ID

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# States for FSM
class QuizCreation(StatesGroup):
    waiting_for_quiz_name = State()
    waiting_for_question_count = State()
    waiting_for_question = State()
    waiting_for_variants = State()
    waiting_for_correct_answer = State()

class QuizTaking(StatesGroup):
    waiting_for_name = State()
    taking_quiz = State()

# Data storage (in production, use a database)
quizzes = {}
quiz_results = {}
users = {}
bi_weekly_rankings = {}  # Store bi-weekly ranking data

class BiWeeklyManager:
    @staticmethod
    def get_current_bi_week():
        """Get current bi-weekly period"""
        now = datetime.now()
        year = now.year
        
        # Calculate which bi-week of the year we're in
        start_of_year = datetime(year, 1, 1)
        days_passed = (now - start_of_year).days
        bi_week_number = (days_passed // 14) + 1
        
        return f"{year}-BW{bi_week_number:02d}"
    
    @staticmethod
    def get_bi_week_dates(bi_week_id):
        """Get start and end dates for a bi-weekly period"""
        year, bw_part = bi_week_id.split('-BW')
        year = int(year)
        bi_week_num = int(bw_part)
        
        start_of_year = datetime(year, 1, 1)
        bi_week_start = start_of_year + timedelta(days=(bi_week_num - 1) * 14)
        bi_week_end = bi_week_start + timedelta(days=13, hours=23, minutes=59, seconds=59)
        
        return bi_week_start, bi_week_end
    
    @staticmethod
    def update_bi_weekly_ranking(user_id, user_name, username, score, total, quiz_name):
        """Update bi-weekly ranking for a user"""
        current_bi_week = BiWeeklyManager.get_current_bi_week()
        
        if current_bi_week not in bi_weekly_rankings:
            bi_weekly_rankings[current_bi_week] = {}
        
        if user_id not in bi_weekly_rankings[current_bi_week]:
            bi_weekly_rankings[current_bi_week][user_id] = {
                'name': user_name,
                'username': username,
                'total_score': 0,
                'total_questions': 0,
                'quiz_count': 0,
                'quizzes': [],
                'first_attempt': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        
        user_data = bi_weekly_rankings[current_bi_week][user_id]
        user_data['name'] = user_name  # Update name in case it changed
        user_data['username'] = username  # Update username
        user_data['total_score'] += score
        user_data['total_questions'] += total
        user_data['quiz_count'] += 1
        user_data['quizzes'].append({
            'quiz_name': quiz_name,
            'score': score,
            'total': total,
            'percentage': round((score/total)*100, 1),
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        user_data['last_attempt'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        user_data['average_percentage'] = round((user_data['total_score']/user_data['total_questions'])*100, 1)
    
    @staticmethod
    def get_current_bi_weekly_ranking():
        """Get current bi-weekly ranking sorted by performance"""
        current_bi_week = BiWeeklyManager.get_current_bi_week()
        
        if current_bi_week not in bi_weekly_rankings:
            return []
        
        ranking_data = []



        for user_id, data in bi_weekly_rankings[current_bi_week].items():
            ranking_data.append({
                'user_id': user_id,
                'name': data['name'],
                'username': data['username'],
                'total_score': data['total_score'],
                'total_questions': data['total_questions'],
                'quiz_count': data['quiz_count'],
                'average_percentage': data['average_percentage'],
                'quizzes': data['quizzes']
            })
        
        # Sort by average percentage (descending), then by total score (descending)
        ranking_data.sort(key=lambda x: (x['average_percentage'], x['total_score']), reverse=True)
        return ranking_data
    
    @staticmethod
    def get_previous_bi_weekly_ranking():
        """Get previous bi-weekly ranking"""
        current_bi_week = BiWeeklyManager.get_current_bi_week()
        year, bw_part = current_bi_week.split('-BW')
        year = int(year)
        bi_week_num = int(bw_part)
        
        if bi_week_num > 1:
            prev_bi_week = f"{year}-BW{bi_week_num-1:02d}"
        else:
            prev_bi_week = f"{year-1}-BW26"  # Last bi-week of previous year
        
        if prev_bi_week not in bi_weekly_rankings:
            return []
        
        ranking_data = []
        for user_id, data in bi_weekly_rankings[prev_bi_week].items():
            ranking_data.append({
                'user_id': user_id,
                'name': data['name'],
                'username': data['username'],
                'average_percentage': data['average_percentage'],
                'total_score': data['total_score'],
                'quiz_count': data['quiz_count']
            })
        
        ranking_data.sort(key=lambda x: (x['average_percentage'], x['total_score']), reverse=True)
        return ranking_data
    
    @staticmethod
    def compare_rankings():
        """Compare current and previous bi-weekly rankings"""
        current_ranking = BiWeeklyManager.get_current_bi_weekly_ranking()
        previous_ranking = BiWeeklyManager.get_previous_bi_weekly_ranking()
        
        # Create position maps
        current_positions = {user['user_id']: i+1 for i, user in enumerate(current_ranking)}
        previous_positions = {user['user_id']: i+1 for i, user in enumerate(previous_ranking)}
        
        comparison = []
        for user in current_ranking:
            user_id = user['user_id']
            current_pos = current_positions[user_id]
            previous_pos = previous_positions.get(user_id, None)
            
            if previous_pos is None:
                change = "🆕 Yangi"
            elif current_pos < previous_pos:
                change = f"📈 +{previous_pos - current_pos}"
            elif current_pos > previous_pos:
                change = f"📉 -{current_pos - previous_pos}"
            else:
                change = "➡️ O'zgarish yo'q"
            
            comparison.append({
                'user': user,
                'current_position': current_pos,
                'previous_position': previous_pos,
                'change': change
            })
        
        return comparison




class QuizManager:
    @staticmethod
    def generate_quiz_code():
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    
    @staticmethod
    def save_quiz(quiz_data):
        code = QuizManager.generate_quiz_code()
        while code in quizzes:
            code = QuizManager.generate_quiz_code()
        quizzes[code] = quiz_data
        return code
    
    @staticmethod
    def get_quiz(code):
        return quizzes.get(code)
    
    @staticmethod
    def save_result(quiz_code, user_name, user_id, username, score, total, answers):
        if quiz_code not in quiz_results:
            quiz_results[quiz_code] = []
        
        result = {
            'user_name': user_name,
            'user_id': user_id,
            'username': username,
            'score': score,
            'total': total,
            'answers': answers,
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        quiz_results[quiz_code].append(result)
        
        # Save user info
        users[user_id] = {
            'name': user_name,
            'username': username,
            'last_seen': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Update bi-weekly ranking
        quiz_name = quizzes[quiz_code]['name']
        BiWeeklyManager.update_bi_weekly_ranking(user_id, user_name, username, score, total, quiz_name)

# Owner keyboard
def get_owner_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Test yaratish", callback_data="create_quiz")],
        [InlineKeyboardButton(text="📊 Testlar natijalari", callback_data="view_results")],
        [InlineKeyboardButton(text="🏆 Ikki haftalik reyting", callback_data="bi_weekly_ranking")],
        [InlineKeyboardButton(text="📈 Reyting taqqoslash", callback_data="compare_rankings")],
        [InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="view_users")],
        [InlineKeyboardButton(text="🗂 Testlarim", callback_data="my_quizzes")]
    ])
    return keyboard

# Quiz selection keyboard for results
def get_quiz_selection_keyboard():
    keyboard = []
    for code, quiz in quizzes.items():
        keyboard.append([InlineKeyboardButton(
            text=f"🎯 {quiz['name']} ({code})",
            callback_data=f"quiz_results_{code}"
        )])
    
    if not keyboard:
        return None
    
    keyboard.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Ranking keyboard
def get_ranking_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Joriy ikki hafta", callback_data="current_ranking")],
        [InlineKeyboardButton(text="📋 Oldingi ikki hafta", callback_data="previous_ranking")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_menu")]
    ])
    return keyboard

# Start command
@dp.message(Command("start"))
async def start_command(message: types.Message):
    if message.from_user.id == OWNER_ID:
        await message.answer(
            "🎮 Test Botga Xush kelibsiz!\n\n"
            "Siz egasiz. Qanday ish qilmoqchisiz:",
            reply_markup=get_owner_keyboard()
        )
    else:
        await message.answer(
            "🎮 Test Botga Xush kelibsiz!\n\n"
            "Test olish uchun quyidagi buyruqdan foydalaning:\n"
            "/quiz [CODE]\n\n"
            "Misol: /quiz ABC123\n\n"
            "Test yaratuvchisidan test kodini oling!"
        )




# Quiz command for users
@dp.message(Command("quiz"))
async def quiz_command(message: types.Message, state: FSMContext):
    if message.from_user.id == OWNER_ID:
        await message.answer("❌ Egalar test ololmaydi. Testlarni boshqarish uchun menyudan foydalaning.")
        return
    
    args = message.text.split()
    if len(args) != 2:
        await message.answer("❌ Iltimos, test kodini taqdim eting.\nMisol: /quiz ABC123")
        return
    
    quiz_code = args[1].upper()
    quiz = QuizManager.get_quiz(quiz_code)
    
    if not quiz:
        await message.answer("❌ Test topilmadi. Iltimos, kodni tekshiring.")
        return
    
    await state.update_data(quiz_code=quiz_code, quiz=quiz)
    await message.answer(
        f"🎯 Testga xush kelibsiz: {quiz['name']}\n\n"
        f"📝 Savollar: {len(quiz['questions'])}\n\n"
        "Iltimos, to'liq ismingizni kiriting:"
    )
    await state.set_state(QuizTaking.waiting_for_name)

# Handle owner callbacks
@dp.callback_query(lambda c: c.from_user.id == OWNER_ID)
async def handle_owner_callbacks(callback: CallbackQuery, state: FSMContext):
    if callback.data == "create_quiz":
        await callback.message.edit_text(
            "📝 Yangi test yaratilyapti...\n\n"
            "Iltimos, test nomini kiriting:"
        )
        await state.set_state(QuizCreation.waiting_for_quiz_name)
    
    elif callback.data == "view_results":
        quiz_keyboard = get_quiz_selection_keyboard()
        if quiz_keyboard:
            await callback.message.edit_text(
                "📊 Natijalarni ko'rish uchun testni tanlang:",
                reply_markup=quiz_keyboard
            )
        else:
            await callback.message.edit_text(
                "📊 Hech qanday test topilmadi.\n\n"
                "Avval test yarating!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_menu")]
                ])
            )
    
    elif callback.data == "bi_weekly_ranking":
        await callback.message.edit_text(
            "🏆 Ikki haftalik reyting\n\n"
            "Qaysi davr reytingini ko'rmoqchisiz?",
            reply_markup=get_ranking_keyboard()
        )
    
    elif callback.data == "current_ranking":
        current_ranking = BiWeeklyManager.get_current_bi_weekly_ranking()
        current_bi_week = BiWeeklyManager.get_current_bi_week()
        
        if current_ranking:
            start_date, end_date = BiWeeklyManager.get_bi_week_dates(current_bi_week)
            ranking_text = f"🏆 Joriy ikki hafta reytingi\n"
            ranking_text += f"📅 {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}\n\n"
            
            for i, user in enumerate(current_ranking[:10], 1):  # Top 10
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                ranking_text += f"{medal} {user['name']}\n"
                if user['username']:
                    ranking_text += f"   @{user['username']}\n"
                ranking_text += f"   📊 {user['average_percentage']}% ({user['total_score']}/{user['total_questions']})\n"
                ranking_text += f"   🎯 {user['quiz_count']} ta test\n\n"
        else:
            ranking_text = f"🏆 Joriy ikki hafta reytingi\n\n"
            ranking_text += "Hali hech kim test topshirmagan."
        
        await callback.message.edit_text(
            ranking_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Orqaga", callback_data="bi_weekly_ranking")]
            ])
        )
    
    elif callback.data == "previous_ranking":
        previous_ranking = BiWeeklyManager.get_previous_bi_weekly_ranking()
        
        if previous_ranking:
            current_bi_week = BiWeeklyManager.get_current_bi_week()
            year, bw_part = current_bi_week.split('-BW')
            year = int(year)
            bi_week_num = int(bw_part)
            
            if bi_week_num > 1:



                prev_bi_week = f"{year}-BW{bi_week_num-1:02d}"
            else:
                prev_bi_week = f"{year-1}-BW26"
            
            start_date, end_date = BiWeeklyManager.get_bi_week_dates(prev_bi_week)
            ranking_text = f"🏆 Oldingi ikki hafta reytingi\n"
            ranking_text += f"📅 {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}\n\n"
            
            for i, user in enumerate(previous_ranking[:10], 1):  # Top 10
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                ranking_text += f"{medal} {user['name']}\n"
                if user['username']:
                    ranking_text += f"   @{user['username']}\n"
                ranking_text += f"   📊 {user['average_percentage']}%\n"
                ranking_text += f"   🎯 {user['quiz_count']} ta test\n\n"
        else:
            ranking_text = f"🏆 Oldingi ikki hafta reytingi\n\n"
            ranking_text += "Oldingi davr uchun ma'lumot yo'q."
        
        await callback.message.edit_text(
            ranking_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Orqaga", callback_data="bi_weekly_ranking")]
            ])
        )
    
    elif callback.data == "compare_rankings":
        comparison = BiWeeklyManager.compare_rankings()
        
        if comparison:
            compare_text = f"📈 Ikki haftalik reyting taqqoslash\n\n"
            
            for item in comparison[:10]:  # Top 10
                user = item['user']
                current_pos = item['current_position']
                change = item['change']
                
                medal = "🥇" if current_pos == 1 else "🥈" if current_pos == 2 else "🥉" if current_pos == 3 else f"{current_pos}."
                compare_text += f"{medal} {user['name']} {change}\n"
                if user['username']:
                    compare_text += f"   @{user['username']}\n"
                compare_text += f"   📊 {user['average_percentage']}% ({user['total_score']}/{user['total_questions']})\n\n"
        else:
            compare_text = "📈 Ikki haftalik reyting taqqoslash\n\n"
            compare_text += "Taqqoslash uchun yetarli ma'lumot yo'q."
        
        await callback.message.edit_text(
            compare_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_menu")]
            ])
        )
    
    elif callback.data == "view_users":
        if users:
            user_list = "👥 Ro'yxatdan o'tgan foydalanuvchilar:\n\n"
            for user_id, user_info in users.items():
                user_list += f"👤 {user_info['name']}\n"
                if user_info.get('username'):
                    user_list += f"📱 @{user_info['username']}\n"
                else:
                    user_list += f"📱 Username yo'q\n"
                user_list += f"🆔 ID: {user_id}\n"
                user_list += f"📅 Oxirgi ko'rish: {user_info['last_seen']}\n\n"
        else:
            user_list = "👥 Hech qanday foydalanuvchi test o'tkazmagan."
        
        await callback.message.edit_text(
            user_list,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_menu")]
            ])
        )
    
    elif callback.data == "my_quizzes":
        if quizzes:
            quiz_list = "🗂 Testlaringiz:\n\n"
            for code, quiz in quizzes.items():
                quiz_list += f"🎯 {quiz['name']}\n"
                quiz_list += f"🔑 Kod: {code}\n"
                quiz_list += f"❓ Savollar: {len(quiz['questions'])}\n\n"
        else:
            quiz_list = "🗂 Hech qanday test yaratilmagan."
        
        await callback.message.edit_text(
            quiz_list,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_menu")]
            ])
        )



    elif callback.data == "back_to_menu":
        await callback.message.edit_text(
            "🎮 Test Botga xush kelibsiz!\n\n"
            "Siz egasiz. Qanday ish qilmoqchisiz:",
            reply_markup=get_owner_keyboard()
        )
    
    elif callback.data.startswith("quiz_results_"):
        quiz_code = callback.data.replace("quiz_results_", "")
        results = quiz_results.get(quiz_code, [])
        quiz = quizzes.get(quiz_code)
        
        if results:
            results_text = f"📊 Natijalar: {quiz['name']}\n\n"
            for i, result in enumerate(results, 1):
                results_text += f"{i}. {result['user_name']}\n"
                if result.get('username'):
                    results_text += f"   @{result['username']}\n"
                else:
                    results_text += f"   Username yo'q\n"
                results_text += f"   ID: {result['user_id']}\n"
                results_text += f"   Ball: {result['score']}/{result['total']}\n"
                results_text += f"   Sana: {result['date']}\n\n"
        else:
            results_text = f"📊 Natijalar: {quiz['name']}\n\n"
            results_text += "Hali hech kim test topshirmagan."
        
        await callback.message.edit_text(
            results_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Orqaga", callback_data="view_results")]
            ])
        )
    
    await callback.answer()

# Handle quiz creation states
@dp.message(QuizCreation.waiting_for_quiz_name)
async def process_quiz_name(message: types.Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return
    
    await state.update_data(quiz_name=message.text)
    await message.answer(
        f"✅ Test nomi: {message.text}\n\n"
        "Qancha savol qo'shmoqchisiz?"
    )
    await state.set_state(QuizCreation.waiting_for_question_count)

@dp.message(QuizCreation.waiting_for_question_count)
async def process_question_count(message: types.Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return
    
    try:
        count = int(message.text)
        if count <= 0:
            await message.answer("❌ Iltimos, musbat raqam kiriting.")
            return
    except ValueError:
        await message.answer("❌ Iltimos, to'g'ri raqam kiriting.")
        return
    
    await state.update_data(
        question_count=count,
        current_question=1,
        questions=[]
    )
    await message.answer(
        f"📝 1-savol {count} dan:\n\n"
        "Iltimos, savolni kiriting:"
    )
    await state.set_state(QuizCreation.waiting_for_question)

@dp.message(QuizCreation.waiting_for_question)
async def process_question(message: types.Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return
    
    data = await state.get_data()
    await state.update_data(current_question_text=message.text)
    await message.answer(
        f"Savol: {message.text}\n\n"
        "Endi 3 ta javob variantini kiriting, har birini alohida xabarda.\n"
        "Variant 1 ni yuboring:"
    )
    await state.update_data(variants=[], variant_count=1)
    await state.set_state(QuizCreation.waiting_for_variants)




@dp.message(QuizCreation.waiting_for_variants)
async def process_variants(message: types.Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return
    
    data = await state.get_data()
    variants = data.get('variants', [])
    variants.append(message.text)
    variant_count = data.get('variant_count', 1)
    
    if variant_count < 3:
        await state.update_data(variants=variants, variant_count=variant_count + 1)
        await message.answer(f"✅ Variant {variant_count}: {message.text}\n\nVariant {variant_count + 1} ni yuboring:")
    else:
        await state.update_data(variants=variants)
        variant_text = "\n".join([f"{i+1}. {v}" for i, v in enumerate(variants)])
        await message.answer(
            f"✅ Hamma variantlar qo'shildi:\n\n{variant_text}\n\n"
            "Qaysi javob to'g'ri? (1, 2, yoki 3 ni kiriting):"
        )
        await state.set_state(QuizCreation.waiting_for_correct_answer)

@dp.message(QuizCreation.waiting_for_correct_answer)
async def process_correct_answer(message: types.Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return
    
    try:
        correct_answer = int(message.text)
        if correct_answer not in [1, 2, 3]:
            await message.answer("❌ Iltimos, 1, 2, yoki 3 ni kiriting.")
            return
    except ValueError:
        await message.answer("❌ Iltimos, to'g'ri raqam kiriting (1, 2, yoki 3).")
        return
    
    data = await state.get_data()
    questions = data.get('questions', [])
    
    question_data = {
        'question': data['current_question_text'],
        'variants': data['variants'],
        'correct_answer': correct_answer - 1  # Convert to 0-based index
    }
    questions.append(question_data)
    
    current_question = data['current_question']
    question_count = data['question_count']
    
    if current_question < question_count:
        await state.update_data(
            questions=questions,
            current_question=current_question + 1
        )
        await message.answer(
            f"✅ Savol {current_question} saqlandi!\n\n"
            f"📝 {current_question + 1}-savol {question_count} dan:\n\n"
            "Iltimos, savolni kiriting:"
        )
        await state.set_state(QuizCreation.waiting_for_question)
    else:
        # Quiz creation complete
        quiz_data = {
            'name': data['quiz_name'],
            'questions': questions,
            'created_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        quiz_code = QuizManager.save_quiz(quiz_data)
        
        await message.answer(
            f"🎉 Test muvaffaqiyatli yaratildi!\n\n"
            f"📝 Test: {quiz_data['name']}\n"
            f"🔑 Kod: {quiz_code}\n"
            f"❓ Savollar: {len(questions)}\n\n"
            f"Ushbu kodni foydalanuvchilar bilan ulashing:\n"
            f"/quiz {quiz_code}",
            reply_markup=get_owner_keyboard()
        )
        await state.clear()




# Handle quiz taking states
@dp.message(QuizTaking.waiting_for_name)
async def process_user_name(message: types.Message, state: FSMContext):
    if message.from_user.id == OWNER_ID:
        return
    
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("❌ Iltimos, to'liq ismingizni kiriting (kamida 2 ta belgi).")
        return
    
    data = await state.get_data()
    await state.update_data(
        user_name=name,
        current_question=0,
        answers=[],
        score=0
    )
    
    quiz = data['quiz']
    question = quiz['questions'][0]
    
    # Create answer buttons
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"A) {question['variants'][0]}", callback_data="answer_0")],
        [InlineKeyboardButton(text=f"B) {question['variants'][1]}", callback_data="answer_1")],
        [InlineKeyboardButton(text=f"C) {question['variants'][2]}", callback_data="answer_2")]
    ])
    
    await message.answer(
        f"👋 Salom, {name}!\n\n"
        f"🎯 Test: {quiz['name']}\n\n"
        f"📝 1-savol {len(quiz['questions'])} dan:\n\n"
        f"{question['question']}",
        reply_markup=keyboard
    )
    await state.set_state(QuizTaking.taking_quiz)

# Handle quiz answers
@dp.callback_query(lambda c: c.data.startswith("answer_"))
async def handle_quiz_answers(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id == OWNER_ID:
        await callback.answer("❌ Ega test yecha olmaydi.")
        return
    
    data = await state.get_data()
    quiz = data['quiz']
    current_question = data['current_question']
    answers = data.get('answers', [])
    score = data.get('score', 0)
    
    # Get selected answer
    selected_answer = int(callback.data.split('_')[1])
    correct_answer = quiz['questions'][current_question]['correct_answer']
    
    # Check if answer is correct
    is_correct = selected_answer == correct_answer
    if is_correct:
        score += 1
    
    answers.append({
        'question': quiz['questions'][current_question]['question'],
        'selected': selected_answer,
        'correct': correct_answer,
        'is_correct': is_correct
    })
    
    current_question += 1
    
    if current_question < len(quiz['questions']):
        # Next question
        question = quiz['questions'][current_question]
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"A) {question['variants'][0]}", callback_data="answer_0")],
            [InlineKeyboardButton(text=f"B) {question['variants'][1]}", callback_data="answer_1")],
            [InlineKeyboardButton(text=f"C) {question['variants'][2]}", callback_data="answer_2")]
        ])
        
        await callback.message.edit_text(
            f"📝 {current_question + 1}-savol {len(quiz['questions'])} dan:\n\n"
            f"{question['question']}",
            reply_markup=keyboard
        )
        
        await state.update_data(
            current_question=current_question,
            answers=answers,
            score=score
        )
    else:
        # Quiz finished
        quiz_code = data['quiz_code']
        user_name = data['user_name']
        total_questions = len(quiz['questions'])
        
        # Save result
        QuizManager.save_result(
            quiz_code, user_name, callback.from_user.id, 
            callback.from_user.username,
            score, total_questions, answers
        )
        
        # Show results to user
        percentage = round((score/total_questions) * 100, 1)
        result_text = f"🎉 Test tugatildi!\n\n"
        result_text += f"👤 Ism: {user_name}\n"
        result_text += f"📊 Ball: {score}/{total_questions}\n"
        result_text += f"📈 Foiz: {percentage}%\n\n"
        
        if score == total_questions:
            result_text += "🏆 Mukammal ball! Tabriklaymiz!"
        elif score >= total_questions * 0.8:
            result_text += "🎯 Ajoyib ish! Zo'r natija!"
        elif score >= total_questions * 0.6:
            result_text += "👍 Yaxshi ish! Davom eting!"



        else:
            result_text += "📚 O'qishni davom ettiring va qayta urinib ko'ring!"
        
        result_text += f"\n\n🏆 Ikki haftalik reytingga qo'shildi!"
        
        await callback.message.edit_text(result_text)
        
        # Send results to owner with bi-weekly ranking info
        current_ranking = BiWeeklyManager.get_current_bi_weekly_ranking()
        user_position = None
        for i, user in enumerate(current_ranking, 1):
            if user['user_id'] == callback.from_user.id:
                user_position = i
                break
        
        owner_text = f"📊 Yangi Test Natijasi!\n\n"
        owner_text += f"🎯 Test: {quiz['name']}\n"
        owner_text += f"👤 Talaba: {user_name}\n"
        if callback.from_user.username:
            owner_text += f"📱 Username: @{callback.from_user.username}\n"
        else:
            owner_text += f"📱 Username yo'q\n"
        owner_text += f"🆔 ID: {callback.from_user.id}\n"
        owner_text += f"📊 Ball: {score}/{total_questions} ({percentage}%)\n"
        owner_text += f"📅 Sana: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        if user_position:
            owner_text += f"\n🏆 Ikki haftalik reytingda: {user_position}-o'rin"
        
        await bot.send_message(OWNER_ID, owner_text)
        await state.clear()
    
    await callback.answer()

# Ranking command for all users
@dp.message(Command("ranking"))
async def ranking_command(message: types.Message):
    current_ranking = BiWeeklyManager.get_current_bi_weekly_ranking()
    current_bi_week = BiWeeklyManager.get_current_bi_week()
    
    if current_ranking:
        start_date, end_date = BiWeeklyManager.get_bi_week_dates(current_bi_week)
        ranking_text = f"🏆 Joriy ikki hafta reytingi\n"
        ranking_text += f"📅 {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}\n\n"
        
        # Show different amount based on user type
        show_count = 20 if message.from_user.id == OWNER_ID else 10
        
        for i, user in enumerate(current_ranking[:show_count], 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            ranking_text += f"{medal} {user['name']}\n"
            ranking_text += f"   📊 {user['average_percentage']}% ({user['total_score']}/{user['total_questions']})\n"
            ranking_text += f"   🎯 {user['quiz_count']} ta test\n"
            
            # Highlight current user
            if user['user_id'] == message.from_user.id:
                ranking_text += "   ⭐️ SIZ\n"
            ranking_text += "\n"
        
        # If user is not in top 10, show their position
        if message.from_user.id != OWNER_ID:
            user_position = None
            user_data = None
            for i, user in enumerate(current_ranking, 1):
                if user['user_id'] == message.from_user.id:
                    user_position = i
                    user_data = user
                    break
            
            if user_position and user_position > 10:
                ranking_text += f"...\n\n"
                ranking_text += f"{user_position}. {user_data['name']} ⭐️ SIZ\n"
                ranking_text += f"   📊 {user_data['average_percentage']}% ({user_data['total_score']}/{user_data['total_questions']})\n"
                ranking_text += f"   🎯 {user_data['quiz_count']} ta test\n"
    else:
        ranking_text = f"🏆 Joriy ikki hafta reytingi\n\n"
        ranking_text += "Hali hech kim test topshirmagan."
    
    await message.answer(ranking_text)

# Main function
async def main():
    print("🤖 Quiz Bot with Bi-weekly Ranking starting...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
