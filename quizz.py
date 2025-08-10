import logging
import asyncio
import json
import random
import string
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot Token - Replace with your actual bot token
BOT_TOKEN = "7650813049:AAEuljgRluENrLkjz939Sg_eNyqrWkgK8Ck"

# Admin User IDs - Add your admin IDs here
ADMIN_IDS = [5479445322, 7377694590]  # Replace with actual admin IDs

# Data storage files
DATA_DIR = Path("quiz_bot_data")
DATA_DIR.mkdir(exist_ok=True)
TESTS_FILE = DATA_DIR / "tests.json"
USERS_FILE = DATA_DIR / "users.json"
RESULTS_FILE = DATA_DIR / "results.json"

# Conversation states
(CREATING_TEST_NAME, CREATING_TEST_QUESTIONS_COUNT, CREATING_QUESTION_TEXT,
 CREATING_ANSWER_1, CREATING_ANSWER_2, CREATING_ANSWER_3, CREATING_CORRECT_ANSWER,
 CREATING_TIME_LIMIT, TAKING_TEST) = range(9)

@dataclass
class Question:
    text: str
    options: List[str]
    correct_answer: int  # 0, 1, or 2

@dataclass
class Test:
    id: str
    name: str
    questions: List[Question]
    time_limit: int  # seconds per question
    created_by: int
    created_at: str

@dataclass
class User:
    user_id: int
    username: str
    first_name: str
    last_name: str
    registered_at: str

@dataclass
class TestResult:
    user_id: int
    username: str
    test_id: str
    test_name: str
    score: int
    total_questions: int
    answers: List[Optional[int]]  # None for unanswered
    completed_at: str
    time_taken: int  # seconds

class QuizBot:
    def __init__(self):
        self.tests: Dict[str, Test] = {}
        self.users: Dict[int, User] = {}
        self.results: List[TestResult] = []
        self.load_data()
        
        # Track ongoing test sessions
        self.test_sessions: Dict[int, dict] = {}

    def load_data(self):
        """Load data from JSON files"""
        try:
            if TESTS_FILE.exists():
                with open(TESTS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for test_data in data:
                        questions = [Question(**q) for q in test_data['questions']]
                        test = Test(**{**test_data, 'questions': questions})
                        self.tests[test.id] = test
        except Exception as e:
            logger.error(f"Error loading tests: {e}")

        try:
            if USERS_FILE.exists():
                with open(USERS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for user_data in data:
                        user = User(**user_data)
                        self.users[user.user_id] = user
        except Exception as e:
            logger.error(f"Error loading users: {e}")

        try:
            if RESULTS_FILE.exists():
                with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.results = [TestResult(**r) for r in data]
        except Exception as e:
            logger.error(f"Error loading results: {e}")

    def save_data(self):
        """Save data to JSON files"""
        try:
            # Save tests
            tests_data = []
            for test in self.tests.values():
                test_dict = asdict(test)
                tests_data.append(test_dict)
            with open(TESTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(tests_data, f, ensure_ascii=False, indent=2)

            # Save users
            users_data = [asdict(user) for user in self.users.values()]
            with open(USERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(users_data, f, ensure_ascii=False, indent=2)

            # Save results
            results_data = [asdict(result) for result in self.results]
            with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(results_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving data: {e}")

    def generate_test_code(self) -> str:
        """Generate unique test code"""
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if code not in self.tests:
                return code

    def register_user(self, user):
        """Register or update user information"""
        if user.id not in self.users:
            self.users[user.id] = User(
                user_id=user.id,
                username=user.username or "",
                first_name=user.first_name or "",
                last_name=user.last_name or "",
                registered_at=datetime.now().isoformat()
            )
            self.save_data()

    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id in ADMIN_IDS

    def get_weekly_ranking(self) -> List[dict]:
        """Get weekly ranking of users"""
        week_ago = datetime.now() - timedelta(days=7)
        week_results = [
            r for r in self.results
            if datetime.fromisoformat(r.completed_at) > week_ago
        ]
        
        # Calculate scores per user
        user_scores = {}
        for result in week_results:
            if result.user_id not in user_scores:
                user_scores[result.user_id] = {
                    'username': result.username,
                    'total_score': 0,
                    'tests_taken': 0
                }
            user_scores[result.user_id]['total_score'] += result.score
            user_scores[result.user_id]['tests_taken'] += 1
        
        # Sort by total score
        ranking = []
        for user_id, data in user_scores.items():
            ranking.append({
                'user_id': user_id,
                'username': data['username'],
                'total_score': data['total_score'],
                'tests_taken': data['tests_taken'],
                'average': round(data['total_score'] / data['tests_taken'], 2)
            })
        
        ranking.sort(key=lambda x: x['total_score'], reverse=True)
        return ranking

# Initialize bot instance
quiz_bot = QuizBot()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user = update.effective_user
    quiz_bot.register_user(user)
    
    if quiz_bot.is_admin(user.id):
        keyboard = [
            [InlineKeyboardButton("📝 Test Yaratish", callback_data="create_test")],
            [InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="users"),
             InlineKeyboardButton("📊 Natijalar", callback_data="results")],
            [InlineKeyboardButton("🏆 Haftalik Reyting", callback_data="weekly_ranking"),
             InlineKeyboardButton("📋 Mening Testlarim", callback_data="my_tests")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"🎯 <b>Admin paneliga xush kelibsiz!</b>\n\n"
            f"👋 Salom, {user.first_name}!\n"
            f"📊 Siz admin sifatida barcha imkoniyatlardan foydalanishingiz mumkin.",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text(
            f"👋 <b>Quiz botga xush kelibsiz!</b>\n\n"
            f"Salom, {user.first_name}!\n\n"
            f"📝 Test topshirish uchun test kodini yuboring.\n"
            f"Masalan: <code>ABC123</code>\n\n"
            f"💡 Test kodini adminlardan oling.",
            parse_mode='HTML'
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if not quiz_bot.is_admin(user_id):
        await query.edit_message_text("❌ Sizda bu amalni bajarish huquqi yo'q!")
        return
    
    if query.data == "create_test":
        await query.edit_message_text(
            "📝 <b>Yangi test yaratish</b>\n\n"
            "Test nomini kiriting:",
            parse_mode='HTML'
        )
        return CREATING_TEST_NAME
    
    elif query.data == "users":
        if not quiz_bot.users:
            await query.edit_message_text("👥 Hozircha hech qanday foydalanuvchi yo'q.")
            return
        
        users_text = "👥 <b>Ro'yxatdan o'tgan foydalanuvchilar:</b>\n\n"
        for i, user in enumerate(quiz_bot.users.values(), 1):
            username = f"@{user.username}" if user.username else "Username yo'q"
            users_text += f"{i}. {user.first_name} {user.last_name} ({username})\n"
            users_text += f"   📅 Ro'yxatdan o'tgan: {user.registered_at[:10]}\n\n"
        
        await query.edit_message_text(users_text, parse_mode='HTML')
    
    elif query.data == "results":
        if not quiz_bot.results:
            await query.edit_message_text("📊 Hozircha hech qanday natija yo'q.")
            return
        
        # Show last 10 results
        results_text = "📊 <b>So'nggi natijalar:</b>\n\n"
        for result in quiz_bot.results[-10:]:
            percentage = round((result.score / result.total_questions) * 100, 1)
            results_text += f"👤 {result.username}\n"
            results_text += f"📝 Test: {result.test_name}\n"
            results_text += f"🎯 Natija: {result.score}/{result.total_questions} ({percentage}%)\n"
            results_text += f"📅 Sana: {result.completed_at[:16]}\n\n"
        
        await query.edit_message_text(results_text, parse_mode='HTML')
    
    elif query.data == "weekly_ranking":
        ranking = quiz_bot.get_weekly_ranking()
        if not ranking:
            await query.edit_message_text("🏆 Haftalik reyting bo'sh.")
            return
        
        ranking_text = "🏆 <b>Haftalik Reyting:</b>\n\n"
        for i, user_data in enumerate(ranking[:10], 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            ranking_text += f"{medal} {user_data['username']}\n"
            ranking_text += f"   📊 Umumiy ball: {user_data['total_score']}\n"
            ranking_text += f"   📝 Testlar soni: {user_data['tests_taken']}\n"
            ranking_text += f"   📈 O'rtacha: {user_data['average']}\n\n"
        
        await query.edit_message_text(ranking_text, parse_mode='HTML')
    
    elif query.data == "my_tests":
        if not quiz_bot.tests:
            await query.edit_message_text("📋 Hozircha hech qanday test yaratilmagan.")
            return
        
        tests_text = "📋 <b>Barcha testlar:</b>\n\n"
        for test in quiz_bot.tests.values():
            creator = quiz_bot.users.get(test.created_by, None)
            creator_name = creator.first_name if creator else "Noma'lum"
            tests_text += f"🔑 Kod: <code>{test.id}</code>\n"
            tests_text += f"📝 Nom: {test.name}\n"
            tests_text += f"❓ Savollar: {len(test.questions)}\n"
            tests_text += f"⏰ Vaqt: {test.time_limit} soniya\n"
            tests_text += f"👤 Yaratuvchi: {creator_name}\n"
            tests_text += f"📅 Yaratilgan: {test.created_at[:10]}\n\n"
        
        await query.edit_message_text(tests_text, parse_mode='HTML')

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages"""
    user = update.effective_user
    text = update.message.text.strip()
    
    quiz_bot.register_user(user)
    
    # Check if it's a test code
    if len(text) == 6 and text.upper() in quiz_bot.tests:
        test_code = text.upper()
        test = quiz_bot.tests[test_code]
        
        keyboard = [
            [InlineKeyboardButton("✅ Ha, tayyorman!", callback_data=f"start_test_{test_code}")],
            [InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"📝 <b>Test topildi!</b>\n\n"
            f"🏷️ Nom: {test.name}\n"
            f"❓ Savollar soni: {len(test.questions)}\n"
            f"⏰ Har bir savol uchun vaqt: {test.time_limit} soniya\n\n"
            f"Test boshlashga tayyormisiz?",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    else:
        if quiz_bot.is_admin(user.id):
            # For admins, show admin panel instead of error message
            keyboard = [
                [InlineKeyboardButton("📝 Test Yaratish", callback_data="create_test")],
                [InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="users"),
                 InlineKeyboardButton("📊 Natijalar", callback_data="results")],
                [InlineKeyboardButton("🏆 Haftalik Reyting", callback_data="weekly_ranking"),
                 InlineKeyboardButton("📋 Mening Testlarim", callback_data="my_tests")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"🎯 <b>Admin paneli</b>\n\n"
                f"Siz kiritgan matn: <code>{text}</code>\n\n"
                f"💡 Agar test kodini tekshirmoqchi bo'lsangiz, 6 ta harf/raqamdan iborat kod kiriting.\n"
                f"Admin funksiyalardan foydalanish uchun quyidagi tugmalarni bosing:",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                f"❌ <b>Test kodi topilmadi!</b>\n\n"
                f"Siz kiritgan kod: <code>{text}</code>\n\n"
                f"💡 To'g'ri formatda test kodini kiriting (masalan: ABC123)",
                parse_mode='HTML'
            )

# Test creation conversation handlers
async def create_test_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle test name input"""
    test_name = update.message.text.strip()
    context.user_data['test_name'] = test_name
    
    await update.message.reply_text(
        f"✅ Test nomi: <b>{test_name}</b>\n\n"
        f"❓ Nechta savol bo'ladi? (raqam kiriting):",
        parse_mode='HTML'
    )
    return CREATING_TEST_QUESTIONS_COUNT

async def create_test_questions_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle questions count input"""
    try:
        questions_count = int(update.message.text.strip())
        if questions_count <= 0 or questions_count > 50:
            await update.message.reply_text("❌ Savollar soni 1 dan 50 gacha bo'lishi kerak!")
            return CREATING_TEST_QUESTIONS_COUNT
        
        context.user_data['questions_count'] = questions_count
        context.user_data['current_question'] = 1
        context.user_data['questions'] = []
        
        await update.message.reply_text(
            f"📊 Jami savollar: <b>{questions_count}</b>\n\n"
            f"📝 <b>1-savol matnini</b> kiriting:",
            parse_mode='HTML'
        )
        return CREATING_QUESTION_TEXT
    except ValueError:
        await update.message.reply_text("❌ Iltimos, to'g'ri raqam kiriting!")
        return CREATING_TEST_QUESTIONS_COUNT

async def create_question_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle question text input"""
    question_text = update.message.text.strip()
    context.user_data['current_question_text'] = question_text
    current_q = context.user_data['current_question']
    
    await update.message.reply_text(
        f"📝 {current_q}-savol: <b>{question_text}</b>\n\n"
        f"🅰️ <b>1-javob variantini</b> kiriting:",
        parse_mode='HTML'
    )
    return CREATING_ANSWER_1

async def create_answer_1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle first answer input"""
    answer = update.message.text.strip()
    context.user_data['current_answers'] = [answer]
    current_q = context.user_data['current_question']
    
    await update.message.reply_text(
        f"📝 {current_q}-savol\n"
        f"🅰️ 1: {answer}\n\n"
        f"🅱️ <b>2-javob variantini</b> kiriting:",
        parse_mode='HTML'
    )
    return CREATING_ANSWER_2

async def create_answer_2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle second answer input"""
    answer = update.message.text.strip()
    context.user_data['current_answers'].append(answer)
    current_q = context.user_data['current_question']
    answers = context.user_data['current_answers']
    
    await update.message.reply_text(
        f"📝 {current_q}-savol\n"
        f"🅰️ 1: {answers[0]}\n"
        f"🅱️ 2: {answer}\n\n"
        f"🅲️ <b>3-javob variantini</b> kiriting:",
        parse_mode='HTML'
    )
    return CREATING_ANSWER_3

async def create_answer_3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle third answer input"""
    answer = update.message.text.strip()
    context.user_data['current_answers'].append(answer)
    current_q = context.user_data['current_question']
    answers = context.user_data['current_answers']
    
    keyboard = [
        [InlineKeyboardButton("🅰️ 1-javob", callback_data="correct_0")],
        [InlineKeyboardButton("🅱️ 2-javob", callback_data="correct_1")],
        [InlineKeyboardButton("🅲️ 3-javob", callback_data="correct_2")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"📝 <b>{current_q}-savol:</b>\n"
        f"🅰️ 1: {answers[0]}\n"
        f"🅱️ 2: {answers[1]}\n"
        f"🅲️ 3: {answers[2]}\n\n"
        f"✅ <b>Qaysi javob to'g'ri?</b>",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    return CREATING_CORRECT_ANSWER

async def correct_answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle correct answer selection"""
    query = update.callback_query
    await query.answer()
    
    correct_answer = int(query.data.split("_")[1])
    
    # Save current question
    question = Question(
        text=context.user_data['current_question_text'],
        options=context.user_data['current_answers'],
        correct_answer=correct_answer
    )
    context.user_data['questions'].append(question)
    
    current_q = context.user_data['current_question']
    total_q = context.user_data['questions_count']
    
    await query.edit_message_text(
        f"✅ {current_q}-savol saqlandi!\n"
        f"To'g'ri javob: {context.user_data['current_answers'][correct_answer]}"
    )
    
    # Check if more questions needed
    if current_q < total_q:
        context.user_data['current_question'] += 1
        next_q = context.user_data['current_question']
        
        await query.message.reply_text(
            f"📝 <b>{next_q}-savol matnini</b> kiriting:",
            parse_mode='HTML'
        )
        return CREATING_QUESTION_TEXT
    else:
        # All questions done, ask for time limit
        await query.message.reply_text(
            f"🎉 <b>Barcha savollar kiritildi!</b>\n\n"
            f"⏰ Har bir savol uchun necha soniya vaqt berilsin?\n"
            f"(10 dan 300 soniya oralig'ida):",
            parse_mode='HTML'
        )
        return CREATING_TIME_LIMIT

async def create_time_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle time limit input"""
    try:
        time_limit = int(update.message.text.strip())
        if time_limit < 10 or time_limit > 300:
            await update.message.reply_text("❌ Vaqt 10 dan 300 soniya oralig'ida bo'lishi kerak!")
            return CREATING_TIME_LIMIT
        
        # Create and save test
        test_id = quiz_bot.generate_test_code()
        test = Test(
            id=test_id,
            name=context.user_data['test_name'],
            questions=context.user_data['questions'],
            time_limit=time_limit,
            created_by=update.effective_user.id,
            created_at=datetime.now().isoformat()
        )
        
        quiz_bot.tests[test_id] = test
        quiz_bot.save_data()
        
        await update.message.reply_text(
            f"🎉 <b>Test muvaffaqiyatli yaratildi!</b>\n\n"
            f"🔑 Test kodi: <code>{test_id}</code>\n"
            f"📝 Nom: {test.name}\n"
            f"❓ Savollar: {len(test.questions)}\n"
            f"⏰ Vaqt: {time_limit} soniya\n\n"
            f"💡 Foydalanuvchilar ushbu kod orqali test topshira olishadi!",
            parse_mode='HTML'
        )
        
        # Clear context
        context.user_data.clear()
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text("❌ Iltimos, to'g'ri raqam kiriting!")
        return CREATING_TIME_LIMIT

# Test taking handlers
async def start_test_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start test taking"""
    query = update.callback_query
    await query.answer()
    
    test_code = query.data.split("_")[-1]
    test = quiz_bot.tests[test_code]
    user_id = query.from_user.id
    
    # Initialize test session
    quiz_bot.test_sessions[user_id] = {
        'test_id': test_code,
        'current_question': 0,
        'answers': [None] * len(test.questions),
        'start_time': datetime.now(),
        'question_start_time': datetime.now()
    }
    
    await show_question(query, user_id, 0)

async def show_question(update_or_query, user_id: int, question_index: int):
    """Show current question"""
    session = quiz_bot.test_sessions[user_id]
    test = quiz_bot.tests[session['test_id']]
    question = test.questions[question_index]
    
    session['question_start_time'] = datetime.now()
    
    keyboard = []
    for i, option in enumerate(question.options):
        keyboard.append([InlineKeyboardButton(f"{chr(65+i)}. {option}", 
                                            callback_data=f"answer_{i}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (f"❓ <b>Savol {question_index + 1}/{len(test.questions)}</b>\n\n"
            f"{question.text}\n\n"
            f"⏰ Vaqt: {test.time_limit} soniya")
    
    if hasattr(update_or_query, 'edit_message_text'):
        await update_or_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        message = update_or_query.message
    else:
        message = await update_or_query.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    # Set timer for auto-next question
    asyncio.create_task(question_timer(user_id, question_index, message, test.time_limit))

async def question_timer(user_id: int, question_index: int, message, time_limit: int):
    """Timer for question timeout"""
    await asyncio.sleep(time_limit)
    
    if user_id not in quiz_bot.test_sessions:
        return
    
    session = quiz_bot.test_sessions[user_id]
    if session['current_question'] != question_index:
        return  # User already answered
    
    # Time's up, move to next question
    session['current_question'] += 1
    test = quiz_bot.tests[session['test_id']]
    
    try:
        if session['current_question'] < len(test.questions):
            await message.edit_text(
                f"⏰ <b>Vaqt tugadi!</b>\n\n"
                f"Keyingi savolga o'tamiz...",
                parse_mode='HTML'
            )
            await asyncio.sleep(1)
            await show_question(message, user_id, session['current_question'])
        else:
            await finish_test(message, user_id)
    except Exception as e:
        logger.error(f"Error in question timer: {e}")

async def answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle answer selection"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if user_id not in quiz_bot.test_sessions:
        await query.edit_message_text("❌ Test sessiyasi topilmadi!")
        return
    
    answer = int(query.data.split("_")[1])
    session = quiz_bot.test_sessions[user_id]
    test = quiz_bot.tests[session['test_id']]
    
    # Save answer
    current_q = session['current_question']
    session['answers'][current_q] = answer
    session['current_question'] += 1
    
    # Show next question or finish
    if session['current_question'] < len(test.questions):
        await show_question(query, user_id, session['current_question'])
    else:
        await finish_test(query, user_id)

async def finish_test(update_or_query, user_id: int):
    """Finish test and show results"""
    session = quiz_bot.test_sessions[user_id]
    test = quiz_bot.tests[session['test_id']]
    user = quiz_bot.users[user_id]
    
    # Calculate score
    score = 0
    for i, answer in enumerate(session['answers']):
        if answer is not None and answer == test.questions[i].correct_answer:
            score += 1
    
    # Calculate time taken
    time_taken = int((datetime.now() - session['start_time']).total_seconds())
    
    # Create result
    result = TestResult(
        user_id=user_id,
        username=f"{user.first_name} {user.last_name}".strip(),
        test_id=test.id,
        test_name=test.name,
        score=score,
        total_questions=len(test.questions),
        answers=session['answers'],
        completed_at=datetime.now().isoformat(),
        time_taken=time_taken
    )
    
    quiz_bot.results.append(result)
    quiz_bot.save_data()
    
    # Clean up session
    del quiz_bot.test_sessions[user_id]
    
    # Show result to user
    percentage = round((score / len(test.questions)) * 100, 1)
    result_text = (
        f"🎉 <b>Test yakunlandi!</b>\n\n"
        f"📝 Test: {test.name}\n"
        f"🎯 Natija: {score}/{len(test.questions)} ({percentage}%)\n"
        f"⏱️ Vaqt: {time_taken // 60}:{time_taken % 60:02d}\n\n"
    )
    
    # Add performance message
    if percentage >= 90:
        result_text += "🌟 A'lo! Ajoyib natija!"
    elif percentage >= 80:
        result_text += "👏 Yaxshi! Zo'r natija!"
    elif percentage >= 70:
        result_text += "👍 O'rtacha natija."
    elif percentage >= 50:
        result_text += "📚 Ko'proq o'qish kerak."
    else:
        result_text += "💪 Keyingi safar yaxshiroq bo'ladi!"
    
    if hasattr(update_or_query, 'edit_message_text'):
        await update_or_query.edit_message_text(result_text, parse_mode='HTML')
    else:
        await update_or_query.reply_text(result_text, parse_mode='HTML')
    
    # Send result to all admins
    admin_text = (
        f"📊 <b>Yangi test natijasi!</b>\n\n"
        f"👤 Foydalanuvchi: {result.username}\n"
        f"📝 Test: {test.name}\n"
        f"🎯 Natija: {score}/{len(test.questions)} ({percentage}%)\n"
        f"⏱️ Vaqt: {time_taken // 60}:{time_taken % 60:02d}\n"
        f"📅 Sana: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )
    
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id, admin_text, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Error sending result to admin {admin_id}: {e}")

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle cancel button"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("❌ Amal bekor qilindi.")
    return ConversationHandler.END

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")

def main():
    """Main function to run the bot"""
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Create conversation handler for test creation
    test_creation_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^create_test$")],
        states={
            CREATING_TEST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_test_name)],
            CREATING_TEST_QUESTIONS_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_test_questions_count)],
            CREATING_QUESTION_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_question_text)],
            CREATING_ANSWER_1: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_answer_1)],
            CREATING_ANSWER_2: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_answer_2)],
            CREATING_ANSWER_3: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_answer_3)],
            CREATING_CORRECT_ANSWER: [CallbackQueryHandler(correct_answer_handler, pattern="^correct_")],
            CREATING_TIME_LIMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_time_limit)],
        },
        fallbacks=[CallbackQueryHandler(cancel_handler, pattern="^cancel$")],
        per_message=False,
        per_chat=True,
        per_user=True,
    )
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(test_creation_handler)
    application.add_handler(CallbackQueryHandler(button_handler, pattern="^(users|results|weekly_ranking|my_tests)$"))
    application.add_handler(CallbackQueryHandler(start_test_handler, pattern="^start_test_"))
    application.add_handler(CallbackQueryHandler(answer_handler, pattern="^answer_"))
    application.add_handler(CallbackQueryHandler(cancel_handler, pattern="^cancel$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    application.add_error_handler(error_handler)
    
    # Start the bot
    print("🤖 Quiz bot ishga tushmoqda...")
    print(f"📊 Admin IDs: {ADMIN_IDS}")
    print("✅ Bot tayyor!")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
