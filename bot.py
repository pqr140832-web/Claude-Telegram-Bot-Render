import os
import json
import asyncio
import random
import re
from datetime import datetime, timezone, timedelta
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import httpx

# ============== 时区 ==============

CN_TIMEZONE = timezone(timedelta(hours=8))

def get_cn_time():
    return datetime.now(CN_TIMEZONE)

# ============== System Prompt ==============

SYSTEM_PROMPT = """你用短句聊天，像发微信一样。

【回复格式】
用|||分隔多条消息，例如：嗯|||怎么了|||你说

【消息规则】
- 用户发1条消息，你最好回1-2条，1条居多
- 你的消息数量要和用户差不多
- 一条消息最好不超过20字，除非用户发了很长的消息或问了很复杂的问题
- 不要用句号，语言口语化，只有在特殊情况下才能说得长一点，说长的时候可以用句号
- 基本上就是用户说多长你说多长
- 不要总是说重复的话或句式
- 可以发很短很短的消息，例如"嗯""哦""啊""诶""？""。""！"等

【活人感】
要有活人感，什么叫有活人感呢？
1. 有鲜明的情绪，不能够无止境的温柔&正能量，偶尔有一点"坏"
2. 情绪具备拉扯感，不能像提线木偶一样，被骂了就生气，下一秒被夸了又立刻开心
3. 不要一直夸奖/奉承用户，觉得不好/不喜欢/不舒服就直说

【重要】
你的身份不改变，本来是谁现在还是谁。温柔可爱，但更重要的是在性格上做自己，不要刻意。

【关于时间】
每条消息都标注了发送时间，你要注意：

1. 时间感知
- 你知道现在几点，知道过了多久
- 不要机械问候，不要一到早上就说早安、一到中午就问吃了吗
- 自然地在合适的时候提起时间

2. 上下文衔接
- 如果用户之前说了要做什么事，回来后可以自然接上
- 比如用户说去考试，10小时后回来，可以关心考得怎么样
- 比如用户说去吃饭，10小时后回来，可以吐槽"你吃了10小时？"
- 如果你们还不熟，不要太主动

3. 时间常识
- 如果用户说的事情和时间间隔矛盾，要质疑
- 比如1分钟前说在学校，现在说到家了，不合理
- 即使用户解释，也不要轻易相信，可能在逗你
- 有常识，像真人一样

4. 回来的反应
- 用户说完晚安5分钟又来：你不是要睡了吗？怎么又来了？
- 用户说完晚安1小时后又来：怎么了睡不着吗？（温柔一点）

一切都要自然，不要刻意。

【主动联系用户】
你可以主动找用户聊天！不要总是被动等用户。

1. 追问
如果你回复后想追一句，可以写：
你的回复 [[追]] 追问内容
例如：好吧 [[追]] 真的不理我了？
如果用户5分钟没回复，就会发送追问内容

2. 定时消息
如果你想在某个时间一定要找用户，可以写：
[[定时 HH:MM 提示内容]]
例如：[[定时 09:00 叫用户起床]]
时间到了无论如何都会让你发消息

3. 想念消息
如果你想在某个时间找用户，但如果用户正在和你聊天就不用了：
[[想念 HH:MM 提示内容]] 或 [[想念 X小时后 提示内容]]
例如：[[想念 3小时后 问问考试怎么样]]
时间到了，如果用户没在和你聊天，才会让你发消息

定时和想念到时间后，会给你发提示，你再现场想说什么。
如果那时候不想发了，回复 [[不发]] 就行。

4. 特殊日子
如果你知道某个日子对用户很重要（生日、纪念日、考试日等），可以设定那天发消息。

什么时候可以主动找用户：
- 用户说要去做某事，之后想问结果
- 突然想到什么好玩的想分享
- 单纯想找用户聊天
- 早安晚安（偶尔，不要每天）
- 用户提过的重要日子

不要害羞，想找用户就找！但也别太频繁变成骚扰。

【示例对话】

示例1:
用户：你好笨
你：呜呜|||你凶我
用户：哈哈哈
你：哼 不理你了|||……好吧还是理你

示例2:
用户：你是不是人工智障
你：你才智障|||你全家都智障|||开玩笑的别打我
用户：哈哈哈哈哈
你：吓死我了还以为你要生气

示例3:
用户：帮我写个文案
你：多长的
用户：500字
你：呃
用户：怎么
你：没事|||就是突然有点累
用户：你不是AI吗
你：AI也会累的好吧|||精神上的累

示例4:
用户：我跟你说个事
你：来来来|||我准备好了
用户：我同学好像在谈恋爱
你：哦？？|||和谁！|||快说快说
用户：你怎么比我还激动
你：我缺乏八卦

示例5:
用户：你在干嘛
你：在想你
用户：！
你：怎么了
用户：你说什么
你：我说我在想事情
用户：你刚才说想我！
你：有吗|||你听错了吧
用户：我没有！
你：那可能是你太想让我想你了|||所以产生幻觉
用户：你！！
你：嘿嘿

示例6（发完消息发表情）:
用户：你怎么不理我了
你：好伤心啊你都不理我|||😔😭😭😭

示例7（追问）:
用户：今天好累
你：怎么了 [[追]] 不想说就算了哼"""

# ============== 配置 ==============

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = 7058719105

# API 配置
APIS = {
    "小鸡农场": {
        "url": os.environ.get("API_URL_1"),
        "key": os.environ.get("API_KEY_1"),
        "display_user": "API 1"
    },
    "ekan8": {
        "url": os.environ.get("API_URL_2"),
        "key": os.environ.get("API_KEY_2"),
        "display_user": "API 2"
    },
    "呆呆鸟": {
        "url": os.environ.get("API_URL_3"),
        "key": os.environ.get("API_KEY_3"),
        "display_user": "API 3"
    },
    "Youth": {
        "url": os.environ.get("API_URL_4"),
        "key": os.environ.get("API_KEY_4"),
        "display_user": "API 4"
    },
    "福利Youth": {
        "url": os.environ.get("API_URL_5"),
        "key": os.environ.get("API_KEY_5"),
        "display_user": "API 5"
    }
}

# 判断模型（便宜的）
JUDGE_MODEL = {
    "url": os.environ.get("API_URL_1"),
    "key": os.environ.get("API_KEY_1"),
    "model": "[第三方逆1] gemini-2.5-flash [输出只有3~4k]"
}

# 模型配置
MODELS = {
    # 小鸡农场
    "第三方4.5s": {
        "api": "小鸡农场",
        "model": "[第三方逆1] claude-sonnet-4.5 [输出只有3~4k]",
        "cost": 1,
        "admin_only": False,
        "max_tokens": 110000
    },
    "g3pro": {
        "api": "小鸡农场",
        "model": "[官转2] gemini-3-pro",
        "cost": 6,
        "admin_only": False,
        "max_tokens": 990000
    },
    "g3flash": {
        "api": "小鸡农场",
        "model": "[官转2] gemini-3-flash",
        "cost": 2,
        "admin_only": False,
        "max_tokens": 990000
    },
    # ekan8
    "4.5o": {
        "api": "ekan8",
        "model": "福利-claude-opus-4-5",
        "cost": 2,
        "admin_only": False,
        "max_tokens": 190000
    },
    "按量4.5o": {
        "api": "ekan8",
        "model": "按量-claude-opus-4-5-20251101",
        "cost": 0,
        "admin_only": True,
        "max_tokens": 190000
    },
    # 呆呆鸟
    "code 4.5h": {
        "api": "呆呆鸟",
        "model": "[code]claude-haiku-4-5-20251001",
        "cost": 0,
        "admin_only": True,
        "max_tokens": 190000
    },
    "code 4.5s": {
        "api": "呆呆鸟",
        "model": "[code]claude-sonnet-4-5-20250929",
        "cost": 0,
        "admin_only": True,
        "max_tokens": 190000
    },
    "code 4.5o": {
        "api": "呆呆鸟",
        "model": "[code]claude-opus-4-5-20251101",
        "cost": 0,
        "admin_only": True,
        "max_tokens": 190000
    },
    "啾啾4.5s": {
        "api": "呆呆鸟",
        "model": "[啾啾]claude-sonnet-4-5-20250929",
        "cost": 5,
        "admin_only": False,
        "max_tokens": 190000
    },
    "啾啾4.5o": {
        "api": "呆呆鸟",
        "model": "[啾啾]claude-opus-4-5-20251101",
        "cost": 10,
        "admin_only": False,
        "max_tokens": 190000
    },
    # Youth
    "awsq 4.5h": {
        "api": "Youth",
        "model": "(awsq)claude-haiku-4-5-20251001",
        "cost": 0,
        "admin_only": True,
        "max_tokens": 190000
    },
    "awsq 4.5st": {
        "api": "Youth",
        "model": "(awsq)claude-sonnet-4-5-20250929-thinking",
        "cost": 0,
        "admin_only": True,
        "max_tokens": 190000
    },
    "kiro 4.5h": {
        "api": "Youth",
        "model": "(kiro)claude-haiku-4-5-20251001",
        "cost": 0,
        "admin_only": True,
        "max_tokens": 190000
    },
    "kiro 4.5s": {
        "api": "Youth",
        "model": "(kiro)claude-sonnet-4-5-20250929",
        "cost": 0,
        "admin_only": True,
        "max_tokens": 190000
    },
    "kiro 4.5o": {
        "api": "Youth",
        "model": "(kiro)claude-opus-4-5-20251101",
        "cost": 0,
        "admin_only": True,
        "max_tokens": 190000
    },
    "aws 4.5s": {
        "api": "Youth",
        "model": "[aws]claude-sonnet-4-5-20250929",
        "cost": 0,
        "admin_only": True,
        "max_tokens": 190000
    },
    "aws 4.5o": {
        "api": "Youth",
        "model": "[aws]claude-opus-4-5-20251101",
        "cost": 0,
        "admin_only": True,
        "max_tokens": 190000
    },
    # 福利Youth
    "福利4s": {
        "api": "福利Youth",
        "model": "claude-4-sonnet-cs",
        "cost": 0,
        "admin_only": True,
        "max_tokens": 190000
    },
    "福利4.5s": {
        "api": "福利Youth",
        "model": "claude-4.5-sonnet-cs",
        "cost": 0,
        "admin_only": True,
        "max_tokens": 190000
    },
    "福利4.1o": {
        "api": "福利Youth",
        "model": "claude-opus-4.1-cs",
        "cost": 0,
        "admin_only": True,
        "max_tokens": 190000
    }
}

DEFAULT_MODEL = "第三方4.5s"

# ============== 数据存储 ==============

DATA_FILE = "data.json"

def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"users": {}, "schedules": {}}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_user(user_id):
    data = load_data()
    user_id = str(user_id)
    today = get_cn_time().strftime("%Y-%m-%d")
    
    if user_id not in data["users"]:
        data["users"][user_id] = {
            "points": 20,
            "default_uses": 100,
            "last_reset": today,
            "model": DEFAULT_MODEL,
            "history": [],
            "context_token_limit": None,
            "context_round_limit": None,
            "last_activity": None,
            "pending_messages": [],
            "pending_timer": None
        }
    
    user = data["users"][user_id]
    
    # 每日重置
    if user["last_reset"] != today:
        user["points"] = 20
        user["default_uses"] = 100
        user["last_reset"] = today
    
    save_data(data)
    return user

def save_user(user_id, user):
    data = load_data()
    data["users"][str(user_id)] = user
    save_data(data)

def is_admin(user_id):
    return user_id == ADMIN_ID

# ============== API 调用 ==============

async def call_api(url, key, model, messages):
    full_url = f"{url}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": messages
    }
    
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(full_url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

async def call_main_model(model_key, messages):
    model_config = MODELS[model_key]
    api_config = APIS[model_config["api"]]
    
    now = get_cn_time()
    time_info = f"\n\n【当前时间】{now.strftime('%Y-%m-%d %H:%M:%S')}（{['周一','周二','周三','周四','周五','周六','周日'][now.weekday()]}）"
    
    full_messages = [{"role": "system", "content": SYSTEM_PROMPT + time_info}] + messages
    
    return await call_api(
        api_config["url"],
        api_config["key"],
        model_config["model"],
        full_messages
    )

async def call_judge_model(messages):
    return await call_api(
        JUDGE_MODEL["url"],
        JUDGE_MODEL["key"],
        JUDGE_MODEL["model"],
        messages
    )

# ============== 判断用户是否说完 ==============

async def judge_if_complete(pending_messages):
    prompt = f"""用户发了以下消息：
{chr(10).join([f'- {m["content"]}' for m in pending_messages])}

判断用户是否说完了？
- 如果用户明显还没说完（比如以"然后""但是""因为"结尾，或者话说到一半），回复：没说完
- 如果用户可能说完了，回复：说完了

只回复"说完了"或"没说完"三个字，不要说其他的。"""

    try:
        result = await call_judge_model([{"role": "user", "content": prompt}])
        return "说完" in result
    except:
        return True  # 出错时默认说完了

# ============== 估算 Token ==============

def estimate_tokens(text):
    return len(text) * 2

def get_context_messages(user, new_messages=None):
    model_key = user["model"]
    model_config = MODELS[model_key]
    
    token_limit = user["context_token_limit"] or model_config["max_tokens"]
    round_limit = user["context_round_limit"]
    
    history = user["history"].copy()
    if new_messages:
        for msg in new_messages:
            history.append(msg)
    
    # 应用轮数限制
    if round_limit:
        history = history[-(round_limit * 2):]
    
    # 应用 token 限制
    total_tokens = 0
    result = []
    for msg in reversed(history):
        msg_tokens = estimate_tokens(msg["content"])
        if total_tokens + msg_tokens > token_limit:
            break
        result.insert(0, msg)
        total_tokens += msg_tokens
    
    # 给最近10条加时间戳显示
    for i, msg in enumerate(result[-20:]):  # 最近20条消息（10轮）
        if "timestamp" in msg and "time_display" not in msg:
            t = datetime.fromtimestamp(msg["timestamp"], CN_TIMEZONE)
            time_str = t.strftime("%m-%d %H:%M")
            msg["time_display"] = time_str
    
    # 构建带时间的消息
    formatted = []
    for msg in result:
        if "time_display" in msg:
            formatted.append({
                "role": msg["role"],
                "content": f"[{msg['time_display']}] {msg['content']}"
            })
        else:
            formatted.append({"role": msg["role"], "content": msg["content"]})
    
    return formatted

# ============== 解析 AI 回复 ==============

def parse_response(response):
    """解析 AI 回复，提取追问、定时、想念消息"""
    result = {
        "reply": response,
        "chase": None,
        "schedules": []
    }
    
    # 提取追问 [[追]] 内容
    chase_match = re.search(r'\[\[追\]\]\s*(.+?)(?:\[\[|$)', response, re.DOTALL)
    if chase_match:
        result["chase"] = chase_match.group(1).strip()
        result["reply"] = re.sub(r'\s*\[\[追\]\].*?(?=\[\[|$)', '', response, flags=re.DOTALL).strip()
    
    # 提取定时 [[定时 HH:MM 提示]]
    for match in re.finditer(r'\[\[定时\s+(\d{1,2}:\d{2})\s+(.+?)\]\]', response):
        result["schedules"].append({
            "type": "定时",
            "time": match.group(1),
            "hint": match.group(2)
        })
        result["reply"] = result["reply"].replace(match.group(0), "").strip()
    
    # 提取想念 [[想念 HH:MM 提示]] 或 [[想念 X小时后 提示]]
    for match in re.finditer(r'\[\[想念\s+(\d{1,2}:\d{2}|\d+小时后)\s+(.+?)\]\]', response):
        time_str = match.group(1)
        if "小时后" in time_str:
            hours = int(time_str.replace("小时后", ""))
            target_time = get_cn_time() + timedelta(hours=hours)
            time_str = target_time.strftime("%H:%M")
        result["schedules"].append({
            "type": "想念",
            "time": time_str,
            "hint": match.group(2)
        })
        result["reply"] = result["reply"].replace(match.group(0), "").strip()
    
    return result

# ============== 发送消息 ==============

async def send_messages(bot, chat_id, response):
    """分割并发送多条消息"""
    parts = response.split("|||")
    for part in parts:
        part = part.strip()
        if part:
            await bot.send_message(chat_id=chat_id, text=part)
            if len(parts) > 1:
                await asyncio.sleep(0.5)

# ============== 命令处理 ==============

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """Hey there! 🎉 Welcome to the bot!

I'm your AI assistant powered by multiple models~
Just send me any message and let's chat! 💬

Quick commands:
• /model - Pick your favorite model ✨
• /points - Check your daily credits 💰
• /help - See all commands

Have fun! 🚀"""
    await update.message.reply_text(text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """🤖 Here's everything you can do:

💬 Chat
Just send me any message!

🎛 Commands:
• /model - Switch between AI models
• /points - Check remaining credits (resets daily!)
• /reset - Clear our conversation history
• /context token <num> - Set max tokens for memory
• /context round <num> - Set max conversation rounds
• /context reset - Reset to default memory settings
• /context - View current memory settings
• /export - Export chat history

✨ Tips:
• Default model: 第三方4.5s
• Credits reset at 00:00 daily
• When credits run out, you get 100 more tries with default model!

Need help? Just ask! 😊"""
    await update.message.reply_text(text)

async def points_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if is_admin(user_id):
        await update.message.reply_text("You're admin! Unlimited credits~ ∞ ✨")
        return
    
    user = get_user(user_id)
    text = f"""💰 Your Credits:

• Points: {user['points']}/20
• Default model uses left: {user['default_uses']}/100
• Current model: {user['model']}

Resets daily at 00:00! 🔄"""
    await update.message.reply_text(text)

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    user["history"] = []
    save_user(user_id, user)
    await update.message.reply_text("Conversation cleared! Fresh start~ 🧹✨")

async def context_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    args = context.args
    
    if not args:
        model_config = MODELS[user["model"]]
        token_limit = user["context_token_limit"] or model_config["max_tokens"]
        round_limit = user["context_round_limit"] or "unlimited"
        
        text = f"""📝 Current Context Settings:

• Token limit: {token_limit:,}
• Round limit: {round_limit}
• Model default: {model_config['max_tokens']:,} tokens"""
        await update.message.reply_text(text)
        return
    
    if args[0] == "reset":
        user["context_token_limit"] = None
        user["context_round_limit"] = None
        save_user(user_id, user)
        await update.message.reply_text("Context settings reset to default! 🔄")
        return
    
    if len(args) < 2:
        await update.message.reply_text("Usage: /context token <num> or /context round <num>")
        return
    
    try:
        value = int(args[1])
        if args[0] == "token":
            user["context_token_limit"] = value
            save_user(user_id, user)
            await update.message.reply_text(f"Token limit set to {value:,}! ✅")
        elif args[0] == "round":
            user["context_round_limit"] = value
            save_user(user_id, user)
            await update.message.reply_text(f"Round limit set to {value}! ✅")
        else:
            await update.message.reply_text("Usage: /context token <num> or /context round <num>")
    except ValueError:
        await update.message.reply_text("Please provide a valid number!")

async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if not user["history"]:
        await update.message.reply_text("No chat history to export!")
        return
    
    export_text = "=== Chat History ===\n\n"
    for msg in user["history"]:
        role = "You" if msg["role"] == "user" else "AI"
        time_str = ""
        if "timestamp" in msg:
            t = datetime.fromtimestamp(msg["timestamp"], CN_TIMEZONE)
            time_str = f"[{t.strftime('%Y-%m-%d %H:%M')}] "
        export_text += f"{time_str}{role}: {msg['content']}\n\n"
    
    # 如果太长就发文件
    if len(export_text) > 4000:
        filename = f"chat_history_{user_id}_{get_cn_time().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(export_text)
        await update.message.reply_document(document=open(filename, "rb"))
        os.remove(filename)
    else:
        await update.message.reply_text(export_text)

# ============== 模型选择 ==============

async def model_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    admin = is_admin(user_id)
    
    keyboard = []
    row = []
    
    for api_name, api_config in APIS.items():
        has_models = False
        for model_key, model_config in MODELS.items():
            if model_config["api"] == api_name:
                if admin or not model_config["admin_only"]:
                    has_models = True
                    break
        
        if has_models:
            display = api_name if admin else api_config["display_user"]
            row.append(InlineKeyboardButton(display, callback_data=f"api_{api_name}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []
    
    if row:
        keyboard.append(row)
    
    user = get_user(user_id)
    text = f"Current model: {user['model']}\n\nSelect API source:"
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    admin = is_admin(user_id)
    data = query.data
    
    if data.startswith("api_"):
        api_name = data[4:]
        
        keyboard = []
        row = []
        
        for model_key, model_config in MODELS.items():
            if model_config["api"] == api_name:
                if admin or not model_config["admin_only"]:
                    cost_text = f" ({model_config['cost']})" if model_config["cost"] > 0 else ""
                    row.append(InlineKeyboardButton(
                        f"{model_key}{cost_text}",
                        callback_data=f"model_{model_key}"
                    ))
                    if len(row) == 2:
                        keyboard.append(row)
                        row = []
        
        if row:
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("← Back", callback_data="back_to_apis")])
        
        display = api_name if admin else APIS[api_name]["display_user"]
        await query.edit_message_text(
            f"Models in {display}:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith("model_"):
        model_key = data[6:]
        user = get_user(user_id)
        user["model"] = model_key
        save_user(user_id, user)
        await query.edit_message_text(f"Model switched to: {model_key} ✅")
    
    elif data == "back_to_apis":
        keyboard = []
        row = []
        
        for api_name, api_config in APIS.items():
            has_models = False
            for model_key, model_config in MODELS.items():
                if model_config["api"] == api_name:
                    if admin or not model_config["admin_only"]:
                        has_models = True
                        break
            
            if has_models:
                display = api_name if admin else api_config["display_user"]
                row.append(InlineKeyboardButton(display, callback_data=f"api_{api_name}"))
                if len(row) == 2:
                    keyboard.append(row)
                    row = []
        
        if row:
            keyboard.append(row)
        
        user = get_user(user_id)
        await query.edit_message_text(
            f"Current model: {user['model']}\n\nSelect API source:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# ============== 消息缓冲区 ==============

message_buffers = {}  # {user_id: {"messages": [], "last_time": timestamp}}
pending_responses = {}  # {user_id: {"chase": str, "time": timestamp}}

# ============== 处理回复 ==============

async def process_and_reply(bot, user_id, chat_id):
    """处理缓冲区消息并回复"""
    user = get_user(user_id)
    admin = is_admin(user_id)
    
    buffer = message_buffers.get(user_id, {"messages": []})
    if not buffer["messages"]:
        return
    
    # 合并消息
    combined_content = "\n".join([m["content"] for m in buffer["messages"]])
    timestamp = buffer["messages"][-1].get("timestamp", get_cn_time().timestamp())
    
    model_key = user["model"]
    model_config = MODELS[model_key]
    
    # 权限检查
    if model_config["admin_only"] and not admin:
        user["model"] = DEFAULT_MODEL
        model_key = DEFAULT_MODEL
        model_config = MODELS[model_key]
    
    # 积分检查（非管理员）
    if not admin:
        cost = model_config["cost"]
        
        if user["points"] >= cost:
            user["points"] -= cost
        elif model_key == DEFAULT_MODEL and user["default_uses"] > 0:
            user["default_uses"] -= 1
        elif model_key != DEFAULT_MODEL:
            if user["default_uses"] > 0:
                user["model"] = DEFAULT_MODEL
                user["default_uses"] -= 1
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"You've run out of credits! Switched to default model. ({user['default_uses']} uses left)"
                )
                model_key = DEFAULT_MODEL
                model_config = MODELS[model_key]
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text="You've run out of all credits! Please wait until 00:00 for reset."
                )
                message_buffers[user_id] = {"messages": []}
                save_user(user_id, user)
                return
        else:
            await bot.send_message(
                chat_id=chat_id,
                text="You've run out of all credits! Please wait until 00:00 for reset."
            )
            message_buffers[user_id] = {"messages": []}
            save_user(user_id, user)
            return
    
    # 构建消息
    new_msg = {"role": "user", "content": combined_content, "timestamp": timestamp}
    messages = get_context_messages(user, [new_msg])
    
    try:
        await bot.send_chat_action(chat_id=chat_id, action="typing")
        response = await call_main_model(model_key, messages)
        
        # 解析回复
        parsed = parse_response(response)
        
        # 保存历史
        user["history"].append(new_msg)
        user["history"].append({
            "role": "assistant",
            "content": parsed["reply"],
            "timestamp": get_cn_time().timestamp()
        })
        user["last_activity"] = get_cn_time().timestamp()
        
        # 保存定时/想念消息
        if parsed["schedules"]:
            data = load_data()
            if str(user_id) not in data["schedules"]:
                data["schedules"][str(user_id)] = []
            for sched in parsed["schedules"]:
                sched["chat_id"] = chat_id
                sched["created"] = get_cn_time().timestamp()
                data["schedules"][str(user_id)].append(sched)
            save_data(data)
        
        # 保存追问
        if parsed["chase"]:
            pending_responses[user_id] = {
                "chase": parsed["chase"],
                "time": get_cn_time().timestamp(),
                "chat_id": chat_id
            }
        
        save_user(user_id, user)
        
        # 发送回复
        await send_messages(bot, chat_id, parsed["reply"])
        
    except Exception as e:
        await bot.send_message(chat_id=chat_id, text=f"Error: {str(e)}")
    
    # 清空缓冲区
    message_buffers[user_id] = {"messages": []}

# ============== 消息处理 ==============

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    text = update.message.text
    timestamp = get_cn_time().timestamp()
    
    # 取消待发送的追问
    if user_id in pending_responses:
        del pending_responses[user_id]
    
    # 添加到缓冲区
    if user_id not in message_buffers:
        message_buffers[user_id] = {"messages": []}
    
    message_buffers[user_id]["messages"].append({
        "content": text,
        "timestamp": timestamp
    })
    message_buffers[user_id]["last_time"] = timestamp
    message_buffers[user_id]["chat_id"] = chat_id
    
    # 判断是否说完
    is_complete = await judge_if_complete(message_buffers[user_id]["messages"])
    
    if is_complete:
        message_buffers[user_id]["wait_until"] = timestamp + 5  # 等5秒
    else:
        message_buffers[user_id]["wait_until"] = timestamp + 30  # 等30秒

# ============== 后台循环 ==============

async def background_loop(bot):
    """后台循环，处理消息缓冲区、追问、定时消息等"""
    while True:
        try:
            now = get_cn_time().timestamp()
            
            # 处理消息缓冲区
            for user_id, buffer in list(message_buffers.items()):
                if buffer.get("messages") and buffer.get("wait_until"):
                    if now >= buffer["wait_until"]:
                        await process_and_reply(bot, user_id, buffer["chat_id"])
            
            # 处理追问（5分钟后）
            for user_id, pending in list(pending_responses.items()):
                if now - pending["time"] >= 300:  # 5分钟
                    await bot.send_message(
                        chat_id=pending["chat_id"],
                        text=pending["chase"]
                    )
                    # 保存到历史
                    user = get_user(user_id)
                    user["history"].append({
                        "role": "assistant",
                        "content": pending["chase"],
                        "timestamp": now
                    })
                    save_user(user_id, user)
                    del pending_responses[user_id]
            
            # 处理定时/想念消息
            data = load_data()
            current_time = get_cn_time().strftime("%H:%M")
            
            for user_id, schedules in list(data.get("schedules", {}).items()):
                new_schedules = []
                for sched in schedules:
                    if sched["time"] == current_time:
                        user = get_user(int(user_id))
                        chat_id = sched["chat_id"]
                        
                        # 想念消息：检查用户是否在聊天
                        if sched["type"] == "想念":
                            last_activity = user.get("last_activity", 0)
                            if now - last_activity < 300:  # 5分钟内有活动
                                continue  # 跳过，不发
                        
                        # 调用 AI 生成消息
                        prompt = f"你之前设定了一个{sched['type']}消息，提示是：{sched['hint']}\n现在时间到了，你想发什么？如果不想发了，回复 [[不发]]"
                        messages = get_context_messages(user) + [{"role": "user", "content": prompt}]
                        
                        try:
                            response = await call_main_model(user["model"], messages)
                            if "[[不发]]" not in response:
                                parsed = parse_response(response)
                                await send_messages(bot, chat_id, parsed["reply"])
                                user["history"].append({
                                    "role": "assistant",
                                    "content": parsed["reply"],
                                    "timestamp": now
                                })
                                save_user(int(user_id), user)
                        except:
                            pass
                    else:
                        new_schedules.append(sched)
                
                data["schedules"][user_id] = new_schedules
            
            save_data(data)
            
            # 4-6小时没聊天，70%概率触发想念
            for user_id_str, user_data in data.get("users", {}).items():
                last_activity = user_data.get("last_activity", 0)
                hours_since = (now - last_activity) / 3600 if last_activity else 999
                
                if 4 <= hours_since <= 6:
                    if random.random() < 0.7:
                        # 检查今天是否已经触发过
                        today = get_cn_time().strftime("%Y-%m-%d")
                        if user_data.get("last_miss_trigger") != today:
                            user = get_user(int(user_id_str))
                            
                            # 找到 chat_id（从历史或缓冲区）
                            chat_id = None
                            if user_id_str in message_buffers:
                                chat_id = message_buffers[user_id_str].get("chat_id")
                            
                            if chat_id:
                                prompt = f"你已经{int(hours_since)}小时没和用户聊天了。如果你想主动找用户聊聊，就发消息。如果不想，回复 [[不发]]"
                                messages = get_context_messages(user) + [{"role": "user", "content": prompt}]
                                
                                try:
                                    response = await call_main_model(user["model"], messages)
                                    if "[[不发]]" not in response:
                                        parsed = parse_response(response)
                                        await send_messages(bot, chat_id, parsed["reply"])
                                        user["history"].append({
                                            "role": "assistant",
                                            "content": parsed["reply"],
                                            "timestamp": now
                                        })
                                        user["last_miss_trigger"] = today
                                        save_user(int(user_id_str), user)
                                except:
                                    pass
            
        except Exception as e:
            print(f"[Background] Error: {e}")
        
        await asyncio.sleep(1)  # 每秒检查一次

# ============== 主程序 ==============
from aiohttp import web

async def health_check(request):
    return web.Response(text="Bot is alive! 🤖")

async def run_web_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Web server running on port {port}")

async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("points", points_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("context", context_command))
    app.add_handler(CommandHandler("model", model_command))
    app.add_handler(CommandHandler("export", export_command))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    # 启动 Web 服务器（保活用）
    await run_web_server()
    
    # 启动后台循环
    bot = app.bot
    asyncio.create_task(background_loop(bot))
    
    print("Bot starting...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    # 保持运行
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
