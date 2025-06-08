import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
import youtube_dl
from pytgcalls import PyTgCalls, idle
from pytgcalls.types import AudioPiped, AudioVideoPiped

# قم بتغيير هذه القيم بمعلومات البوت الخاصة بك
API_ID = 21100923
API_HASH = "32ad1f2eb62a60301e7bbcdf91c43641"
BOT_TOKEN = "7881688759:AAFNZwzFQhfRVEk1ceJ7E21JjbJH6Pmo7HM"

DOWNLOAD_PATH = "downloads/"
LOCAL_MUSIC_PATH = "local_music/"

if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)
if not os.path.exists(LOCAL_MUSIC_PATH):
    os.makedirs(LOCAL_MUSIC_PATH)
    print(f"ملاحظة: المجلد '{LOCAL_MUSIC_PATH}' غير موجود. يرجى وضع ملفات الموسيقى فيه.")

app = Client(
    "music_player_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# تهيئة PyTgCalls
pytgcalls = PyTgCalls(app)

# قاموس لتخزين قوائم الانتظار
queue = {}
# قاموس لتخزين حالة التشغيل الحالية
active_chats = {} # لتتبع الدردشات الصوتية النشطة

async def play_next_in_queue(chat_id: int):
    if queue.get(chat_id) and queue[chat_id]:
        audio_info = queue[chat_id].pop(0)
        file_path = audio_info["file_path"]
        title = audio_info["title"]

        try:
            # الانضمام إلى الدردشة الصوتية إذا لم يكن البوت فيها
            if chat_id not in active_chats or not pytgcalls.get_active_call(chat_id):
                await pytgcalls.join_group_call(
                    chat_id,
                    AudioPiped(file_path),
                    # يمكنك إضافة VideoPiped إذا كنت تريد دعم الفيديو أيضًا
                )
                await app.send_message(chat_id, f"🎵 انضممت إلى الدردشة الصوتية وجاري تشغيل: **{title}**")
            else:
                await pytgcalls.change_stream(
                    chat_id,
                    AudioPiped(file_path)
                )
                await app.send_message(chat_id, f"🎵 جاري تشغيل الأغنية التالية: **{title}**")

            active_chats[chat_id] = {
                "playing": title,
                "file_path": file_path # نحتفظ بالمسار لحذفه لاحقًا إذا كان مؤقتًا
            }

            # لا يوجد 'تم انتهاء قائمة التشغيل' هنا مباشرة، بل عند انتهاء قائمة الانتظار
            # pytgcalls لديها معالجات أحداث لانتهاء التشغيل
            
            # (اختياري) يمكنك حذف الملف بعد وقت معين أو عند بدء أغنية جديدة
            # إذا كان الملف مؤقتًا من يوتيوب
            if not audio_info.get("is_local", False) and os.path.exists(file_path):
                 # يمكنك تنفيذ هذا في معالج أحداث لانتهاء التشغيل أو بعد التأكد من التشغيل
                 # أو بعد تخطي الأغنية
                pass # لا نحذف هنا لتجنب المشاكل، نحذف عند انتهاء التشغيل الفعلي

        except Exception as e:
            await app.send_message(chat_id, f"❌ حدث خطأ أثناء تشغيل الصوت في الدردشة الصوتية: `{e}`")
            print(f"خطأ في play_next_in_queue: {e}")
            del active_chats[chat_id] # إزالة من الدردشات النشطة إذا فشل
            # حاول تشغيل الأغنية التالية إذا فشلت هذه
            asyncio.create_task(play_next_in_queue(chat_id))
    else:
        if chat_id in active_chats:
            await pytgcalls.leave_group_call(chat_id)
            del active_chats[chat_id]
        await app.send_message(chat_id, "✅ انتهت قائمة التشغيل. غادرت الدردشة الصوتية.")

# معالج لانتهاء تشغيل أغنية في الدردشة الصوتية
@pytgcalls.on_stream_end()
async def stream_end_handler(client, update):
    chat_id = update.chat_id
    if chat_id in active_chats:
        # حذف الملف المؤقت إذا كان من يوتيوب
        if not active_chats[chat_id].get("is_local", False) and os.path.exists(active_chats[chat_id]["file_path"]):
            os.remove(active_chats[chat_id]["file_path"])
            print(f"تم حذف الملف الصوتي المؤقت {active_chats[chat_id]['file_path']}")
        
        active_chats[chat_id]["playing"] = None
        # بدء تشغيل الأغنية التالية في قائمة الانتظار
        asyncio.create_task(play_next_in_queue(chat_id))

# الأوامر الأخرى ستحتاج إلى التعديل لاستدعاء play_next_in_queue

@app.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    await message.reply_text(
        "👋 مرحبًا بك في بوت تشغيل الموسيقى في الدردشات الصوتية! "
        "أرسل لي رابط يوتيوب أو اسم أغنية لكي أقوم بتشغيلها (`/play`).\n"
        "لتشغيل أغنية من مجلد الموسيقى المحلي الخاص بي، استخدم `/local_play`.\n"
        "لعرض الأغاني المحلية المتاحة: `/list_local`\n"
        "لاستخدامي في مجموعة أو قناة، أضفني كمسؤول."
    )

@app.on_message(filters.command("play") & (filters.group | filters.channel))
async def play_command(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("الرجاء تقديم رابط يوتيوب أو اسم أغنية.\nمثال: `/play Despacito` أو `/play https://www.youtube.com/watch?v=kJQP7kiw5Fk`")
        return

    query = " ".join(message.command[1:])
    chat_id = message.chat.id

    await message.reply_text(f"⏳ جاري البحث عن: `{query}`...")

    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': os.path.join(DOWNLOAD_PATH, '%(title)s.%(ext)s'),
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
        }

        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            if 'entries' in info:
                info = info['entries'][0]
            
            file_path = ydl.prepare_filename(info)
            ydl.download([query])

            audio_title = info.get('title', 'غير معروف')

            if chat_id not in queue:
                queue[chat_id] = []
            
            queue[chat_id].append({"file_path": file_path, "title": audio_title, "is_local": False})

            # هنا نستدعي play_next_in_queue بدلاً من process_queue
            if chat_id not in active_chats or active_chats[chat_id].get("playing") is None:
                await play_next_in_queue(chat_id)
            else:
                await message.reply_text(f"➕ تم إضافة **{audio_title}** إلى قائمة الانتظار.")

    except Exception as e:
        await message.reply_text(f"❌ حدث خطأ أثناء البحث أو التنزيل: `{e}`")
        print(f"خطأ في أمر /play: {e}")


@app.on_message(filters.command("local_play") & (filters.group | filters.channel))
async def local_play_command(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("الرجاء تقديم رقم الأغنية من قائمة `/list_local` أو اسمها كاملاً.\nمثال: `/local_play 1` أو `/local_play My_Awesome_Song.mp3`")
        return

    query = " ".join(message.command[1:])
    chat_id = message.chat.id
    
    music_files = [f for f in os.listdir(LOCAL_MUSIC_PATH) if f.endswith(('.mp3', '.wav', '.ogg', '.flac', '.m4a'))]
    
    selected_file = None
    if query.isdigit():
        index = int(query) - 1
        if 0 <= index < len(music_files):
            selected_file = music_files[index]
        else:
            await message.reply_text("❌ رقم الأغنية غير صالح. استخدم `/list_local` لمعرفة الأرقام الصحيحة.")
            return
    else:
        for file_name in music_files:
            if query.lower() in file_name.lower():
                selected_file = file_name
                break
        if not selected_file:
            await message.reply_text(f"❌ لم يتم العثور على أغنية باسم `{query}` في المجلد المحلي. يرجى التأكد من الاسم أو استخدام `/list_local`.")
            return

    full_path = os.path.join(LOCAL_MUSIC_PATH, selected_file)

    if chat_id not in queue:
        queue[chat_id] = []
    
    queue[chat_id].append({"file_path": full_path, "title": selected_file, "is_local": True})

    # هنا نستدعي play_next_in_queue بدلاً من process_queue
    if chat_id not in active_chats or active_chats[chat_id].get("playing") is None:
        await play_next_in_queue(chat_id)
    else:
        await message.reply_text(f"➕ تم إضافة **{selected_file}** إلى قائمة الانتظار.")


@app.on_message(filters.command("skip") & (filters.group | filters.channel))
async def skip_command(client: Client, message: Message):
    chat_id = message.chat.id
    if queue.get(chat_id) and queue[chat_id]:
        await message.reply_text("⏩ تخطي الأغنية الحالية...")
        # PyTgCalls لا تسمح بتخطي فوري إلا ببدء تشغيل أغنية جديدة.
        # لذا، سنقوم بتشغيل الأغنية التالية مباشرة
        asyncio.create_task(play_next_in_queue(chat_id))
    elif chat_id in active_chats and active_chats[chat_id].get("playing"):
        await message.reply_text("لا توجد أغاني في قائمة الانتظار، سأغادر الدردشة الصوتية.")
        await pytgcalls.leave_group_call(chat_id)
        del active_chats[chat_id]
    else:
        await message.reply_text("لا توجد أغاني في قائمة التشغيل حاليًا.")

@app.on_message(filters.command("stop") & (filters.group | filters.channel))
async def stop_command(client: Client, message: Message):
    chat_id = message.chat.id
    if chat_id in active_chats:
        queue[chat_id].clear() # مسح قائمة الانتظار
        await pytgcalls.leave_group_call(chat_id)
        del active_chats[chat_id]
        await message.reply_text("⏹️ تم إيقاف التشغيل ومسح قائمة الانتظار. غادرت الدردشة الصوتية.")
    else:
        await message.reply_text("لا يوجد شيء قيد التشغيل حاليًا في الدردشة الصوتية.")

# ... (بقية الأوامر مثل list_local و queue يمكن أن تبقى كما هي مع تعديلات بسيطة)
@app.on_message(filters.command("queue") & (filters.group | filters.channel))
async def show_queue_command(client: Client, message: Message):
    chat_id = message.chat.id
    current_playing = active_chats.get(chat_id, {}).get("playing")
    
    if queue.get(chat_id) and len(queue[chat_id]) > 0:
        msg = "🎶 **قائمة الانتظار:**\n"
        if current_playing:
            msg += f"▶️ قيد التشغيل الآن: **{current_playing}**\n"
        
        for i, audio_info in enumerate(queue[chat_id]):
            msg += f"{i+1}. {audio_info['title']}\n"
        await message.reply_text(msg)
    else:
        if current_playing:
            await message.reply_text(f"🎶 قيد التشغيل الآن: **{current_playing}**\nلا توجد أغاني أخرى في قائمة الانتظار.")
        else:
            await message.reply_text("❌ قائمة التشغيل فارغة.")

# ابدأ البوت و PyTgCalls
print("البوت جاهز للعمل...")
pytgcalls.start()
app.run()
idle() # للحفاظ على البوت يعمل إلى الأبد
