import os
import io
import re
import json
import asyncio
import aiohttp
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# ==================== CONFIGURATION ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable not set!")

# Free video generation APIs
# Note: Most free video generation APIs are limited. We'll use:
# 1. Pollinations.ai for image generation (free, no API key)
# 2. Replicate.com (requires API key, free tier available)
# 3. HuggingFace (requires API key, free tier available)

# For this bot, we'll use Pollinations.ai to generate images
# and then combine them into a simple video concept
POLLINATIONS_URL = "https://image.pollinations.ai/prompt/"

# User sessions
user_sessions = {}
video_history = {}

# ==================== VIDEO GENERATION FUNCTIONS ====================
async def generate_image(prompt: str, size: str = "512x512"):
    """Generate an image using Pollinations.ai"""
    try:
        clean_prompt = prompt.strip().replace(" ", "%20")
        width, height = size.split("x")
        
        url = f"{POLLINATIONS_URL}{clean_prompt}?width={width}&height={height}&nologo=true&seed={int(datetime.now().timestamp())}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=30) as response:
                if response.status == 200:
                    return await response.read()
                else:
                    print(f"API Error: {response.status}")
                    return None
    except asyncio.TimeoutError:
        print("Generation timeout")
        return None
    except Exception as e:
        print(f"Generation error: {e}")
        return None

def generate_video_concept(prompt: str):
    """Generate a video concept/storyboard"""
    scenes = []
    
    # Split prompt into scenes (simple implementation)
    words = prompt.split()
    if len(words) > 10:
        # Create multiple scenes from the prompt
        scene_1 = " ".join(words[:len(words)//3])
        scene_2 = " ".join(words[len(words)//3:2*len(words)//3])
        scene_3 = " ".join(words[2*len(words)//3:])
        scenes = [scene_1, scene_2, scene_3]
    else:
        scenes = [prompt]
    
    return scenes

def detect_video_type(prompt: str):
    """Detect what type of video to generate"""
    prompt_lower = prompt.lower()
    
    if any(word in prompt_lower for word in ['nature', 'landscape', 'sunset', 'mountain', 'forest', 'ocean']):
        return "Nature"
    elif any(word in prompt_lower for word in ['city', 'urban', 'street', 'building', 'skyscraper']):
        return "Urban"
    elif any(word in prompt_lower for word in ['fantasy', 'dragon', 'castle', 'magic', 'wizard']):
        return "Fantasy"
    elif any(word in prompt_lower for word in ['space', 'galaxy', 'planet', 'star', 'astronaut']):
        return "Space"
    elif any(word in prompt_lower for word in ['cartoon', 'anime', 'character', 'animation']):
        return "Cartoon"
    else:
        return "General"

# ==================== KEYBOARD FUNCTIONS ====================
def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("🎬 Generate Video", callback_data="generate")],
        [InlineKeyboardButton("🖼️ Generate Image", callback_data="image")],
        [InlineKeyboardButton("📋 Video History", callback_data="history")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_video_type_keyboard():
    keyboard = [
        [InlineKeyboardButton("🌅 Nature", callback_data="type_nature")],
        [InlineKeyboardButton("🏙️ Urban", callback_data="type_urban")],
        [InlineKeyboardButton("🐉 Fantasy", callback_data="type_fantasy")],
        [InlineKeyboardButton("🚀 Space", callback_data="type_space")],
        [InlineKeyboardButton("🎨 Cartoon", callback_data="type_cartoon")],
        [InlineKeyboardButton("🎲 Random", callback_data="type_random")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="back")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_size_keyboard():
    keyboard = [
        [InlineKeyboardButton("🔲 512x512", callback_data="size_512")],
        [InlineKeyboardButton("🔳 768x768", callback_data="size_768")],
        [InlineKeyboardButton("⬜ 1024x1024", callback_data="size_1024")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="back")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_result_keyboard():
    keyboard = [
        [InlineKeyboardButton("🎬 New Video", callback_data="generate")],
        [InlineKeyboardButton("🖼️ New Image", callback_data="image")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="back")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ==================== COMMAND HANDLERS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    
    # Initialize user session
    user_id = str(user.id)
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    if user_id not in video_history:
        video_history[user_id] = []
    
    welcome_message = (
        f"🎬 Welcome {user.first_name} to **VidForgeBot**!\n\n"
        "Your AI video and image generation companion!\n\n"
        "**✨ Features:**\n"
        "• 🎬 Generate videos from text prompts\n"
        "• 🖼️ Generate images from text descriptions\n"
        "• 🎯 Multiple video styles (Nature, Urban, Fantasy, Space, Cartoon)\n"
        "• 📋 View generation history\n"
        "• 🔍 Auto-detect video type\n\n"
        "**🎯 Quick Start:**\n"
        "• Click 'Generate Video' and enter a description\n"
        "• Click 'Generate Image' for single images\n"
        "• Choose a video style or use auto-detect\n\n"
        "**📝 Example Prompts:**\n"
        "• 'A beautiful sunset over mountains'\n"
        "• 'Futuristic city with flying cars'\n"
        "• 'A dragon flying over a castle'\n\n"
        "⬇️ Start creating now!"
    )
    
    await update.message.reply_text(
        welcome_message,
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = (
        "📖 **VidForgeBot User Guide**\n\n"
        "**🎬 Generate Video**\n"
        "• Click 'Generate Video'\n"
        "• Choose a video style\n"
        "• Enter a description\n"
        "• Get AI-generated video frames\n\n"
        "**🖼️ Generate Image**\n"
        "• Click 'Generate Image'\n"
        "• Enter a description\n"
        "• Choose size\n"
        "• Get AI-generated image\n\n"
        "**🎯 Video Styles**\n"
        "• **Nature:** Landscapes, sunsets, mountains\n"
        "• **Urban:** Cities, streets, buildings\n"
        "• **Fantasy:** Dragons, castles, magic\n"
        "• **Space:** Galaxies, planets, astronauts\n"
        "• **Cartoon:** Animated characters, scenes\n\n"
        "**Commands**\n"
        "/start - Start the bot\n"
        "/help - Show this help\n"
        "/generate - Generate a video\n"
        "/image - Generate an image"
    )
    
    await update.message.reply_text(
        help_text,
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /generate command"""
    await update.message.reply_text(
        "🎬 **Video Generation**\n\n"
        "Choose a video style or enter your description:\n\n"
        "Example: 'A beautiful sunset over mountains'",
        parse_mode="Markdown",
        reply_markup=get_video_type_keyboard()
    )

async def image_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /image command"""
    await update.message.reply_text(
        "🖼️ **Image Generation**\n\n"
        "Please enter a description of the image you want to generate.\n\n"
        "Example: 'A cat wearing a spacesuit on Mars'",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )
    user_id = str(update.effective_user.id)
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    user_sessions[user_id]["action"] = "image_prompt"

# ==================== CALLBACK HANDLERS ====================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button presses"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = str(update.effective_user.id)
    
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    
    if data == "generate":
        await query.edit_message_text(
            "🎬 **Video Generation**\n\n"
            "Choose a video style or enter your description:\n\n"
            "Example: 'A beautiful sunset over mountains'",
            parse_mode="Markdown",
            reply_markup=get_video_type_keyboard()
        )
        user_sessions[user_id]["action"] = "video"
    
    elif data == "image":
        await query.edit_message_text(
            "🖼️ **Image Generation**\n\n"
            "Choose image size:",
            parse_mode="Markdown",
            reply_markup=get_size_keyboard()
        )
        user_sessions[user_id]["action"] = "image"
    
    elif data.startswith("type_"):
        video_type = data.replace("type_", "")
        user_sessions[user_id]["video_type"] = video_type
        user_sessions[user_id]["action"] = "video_prompt"
        
        type_display = {
            "nature": "🌅 Nature",
            "urban": "🏙️ Urban",
            "fantasy": "🐉 Fantasy",
            "space": "🚀 Space",
            "cartoon": "🎨 Cartoon",
            "random": "🎲 Random"
        }.get(video_type, "General")
        
        await query.edit_message_text(
            f"✅ Video style set to: **{type_display}**\n\n"
            "Now enter your video description:\n\n"
            "Example: 'A beautiful sunset over mountains'",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
    
    elif data.startswith("size_"):
        size_map = {
            "size_512": "512x512",
            "size_768": "768x768",
            "size_1024": "1024x1024"
        }
        user_sessions[user_id]["image_size"] = size_map.get(data, "512x512")
        user_sessions[user_id]["action"] = "image_prompt"
        
        await query.edit_message_text(
            f"✅ Size set to: **{user_sessions[user_id]['image_size']}**\n\n"
            "Now enter your image description:\n\n"
            "Example: 'A cat wearing a spacesuit on Mars'",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
    
    elif data == "history":
        history = video_history.get(user_id, [])
        if not history:
            await query.edit_message_text(
                "📋 **No generation history yet!**\n\n"
                "Generate a video or image to build your history.",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
            return
        
        history_text = "📋 **Recent Generations**\n\n"
        for i, entry in enumerate(history[-10:], 1):
            timestamp = entry.get("timestamp", "Unknown")
            prompt = entry.get("prompt", "")[:40]
            gtype = entry.get("type", "Unknown")
            history_text += f"{i}. [{gtype}] {prompt}...\n"
        
        await query.edit_message_text(
            history_text,
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
    
    elif data == "help":
        await help_command(update, context)
    
    elif data == "back":
        await query.edit_message_text(
            "🏠 **Main Menu**\n\n"
            "What would you like to create?",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        user_sessions[user_id] = {}

# ==================== MESSAGE HANDLERS ====================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages"""
    user_id = str(update.effective_user.id)
    text = update.message.text.strip()
    
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    
    action = user_sessions[user_id].get("action", "")
    
    if action == "video_prompt":
        # Process video generation
        processing_msg = await update.message.reply_text(
            "🎬 **Generating video frames...**\n\n"
            "⏳ This may take 30-60 seconds...",
            parse_mode="Markdown"
        )
        
        # Generate scenes
        scenes = generate_video_concept(text)
        video_type = user_sessions[user_id].get("video_type", "random")
        
        if video_type == "random":
            video_type = detect_video_type(text)
        else:
            # Add type prefix to prompt for better results
            type_prefix = {
                "nature": "natural landscape",
                "urban": "city scene",
                "fantasy": "fantasy world",
                "space": "space scene",
                "cartoon": "cartoon style"
            }.get(video_type, "")
            
            if type_prefix:
                text = f"{type_prefix}, {text}"
        
        # Generate images for each scene
        generated_images = []
        for i, scene in enumerate(scenes):
            scene_prompt = f"{text}, scene {i+1}"
            image_data = await generate_image(scene_prompt, "512x512")
            if image_data:
                generated_images.append((scene_prompt, image_data))
            await asyncio.sleep(2)  # Rate limiting
        
        await processing_msg.delete()
        
        if generated_images:
            # Save to history
            if user_id not in video_history:
                video_history[user_id] = []
            video_history[user_id].append({
                "timestamp": datetime.now().isoformat(),
                "prompt": text,
                "type": "Video"
            })
            
            # Send results
            await update.message.reply_text(
                f"🎬 **Video Generated!**\n\n"
                f"📝 **Prompt:** {text}\n"
                f"🎯 **Style:** {video_type.title()}\n"
                f"📊 **Scenes:** {len(generated_images)}\n\n"
                f"💡 Here are the key frames from your video:",
                parse_mode="Markdown"
            )
            
            for i, (scene_prompt, image_data) in enumerate(generated_images[:5]):
                await update.message.reply_photo(
                    photo=io.BytesIO(image_data),
                    caption=f"🎬 Scene {i+1}: {scene_prompt[:50]}...",
                    reply_markup=get_result_keyboard() if i == len(generated_images) - 1 else None
                )
        else:
            await update.message.reply_text(
                "❌ **Failed to generate video**\n\n"
                "Please try:\n"
                "• A different description\n"
                "• Shorter prompt\n"
                "• Waiting a few seconds and retrying",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
        
        user_sessions[user_id]["action"] = None
    
    elif action == "image_prompt":
        # Process image generation
        size = user_sessions[user_id].get("image_size", "512x512")
        
        processing_msg = await update.message.reply_text(
            f"🖼️ **Generating image...**\n\n"
            f"📝 Prompt: {text}\n"
            f"📐 Size: {size}\n\n"
            f"⏳ Please wait 10-20 seconds...",
            parse_mode="Markdown"
        )
        
        image_data = await generate_image(text, size)
        
        await processing_msg.delete()
        
        if image_data:
            # Save to history
            if user_id not in video_history:
                video_history[user_id] = []
            video_history[user_id].append({
                "timestamp": datetime.now().isoformat(),
                "prompt": text,
                "type": "Image"
            })
            
            await update.message.reply_photo(
                photo=io.BytesIO(image_data),
                caption=f"🖼️ **Image Generated!**\n\n"
                       f"📝 **Prompt:** {text}\n"
                       f"📐 **Size:** {size}\n\n"
                       f"💡 Click below to generate more!",
                parse_mode="Markdown",
                reply_markup=get_result_keyboard()
            )
        else:
            await update.message.reply_text(
                "❌ **Failed to generate image**\n\n"
                "Please try:\n"
                "• A different description\n"
                "• Shorter prompt\n"
                "• Waiting a few seconds and retrying",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
        
        user_sessions[user_id]["action"] = None
    
    else:
        # Default response
        await update.message.reply_text(
            "👋 **Use the buttons below!**\n\n"
            "I can:\n"
            "• 🎬 Generate videos from text\n"
            "• 🖼️ Generate images from text\n\n"
            "Click 'Generate Video' or 'Generate Image' to get started!",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )

# ==================== MAIN FUNCTION ====================
def main():
    """Start the bot"""
    print("=" * 50)
    print("🎬 Starting VidForgeBot...")
    print("🖼️ Ready to generate videos and images!")
    print("=" * 50)
    
    # Build application
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .connect_timeout(60.0)
        .read_timeout(60.0)
        .build()
    )
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("generate", generate_command))
    application.add_handler(CommandHandler("image", image_command))
    
    # Add callback handler for buttons
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Add message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Start the bot
    print("✅ Bot is running! Press Ctrl+C to stop.")
    print("=" * 50)
    application.run_polling()

if __name__ == "__main__":
    main()
