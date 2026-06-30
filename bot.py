import os
import io
import re
import asyncio
import aiohttp
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# ==================== CONFIGURATION ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable not set!")

# Get API keys from environment
REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN")
HUGGINGFACE_API_TOKEN = os.environ.get("HUGGINGFACE_API_TOKEN")

# Check if Replicate is available
REPLICATE_AVAILABLE = bool(REPLICATE_API_TOKEN)

# User sessions
user_sessions = {}
video_history = {}

# ==================== VIDEO GENERATION FUNCTIONS ====================

async def generate_video_replicate(prompt: str, duration: int = 3):
    """Generate video using Replicate API"""
    if not REPLICATE_AVAILABLE:
        return None
    
    try:
        import replicate
        
        # Use Stable Video Diffusion model
        # This generates a short video from text prompt
        output = replicate.run(
            "stability-ai/stable-video-diffusion:3f0457e4619daac51203dedb472816fd4af51f3149fa7a9e0b5ffcf1b8172438",
            input={
                "prompt": prompt,
                "num_frames": 14,
                "fps": 7,
                "motion_bucket_id": 127,
                "cond_aug": 0.02,
                "decoding_t": 7,
                "seed": 0,
            }
        )
        
        # Replicate returns a URL or file
        if output:
            # Download the video
            async with aiohttp.ClientSession() as session:
                async with session.get(output, timeout=60) as response:
                    if response.status == 200:
                        return await response.read()
        return None
    except Exception as e:
        print(f"Replicate video generation error: {e}")
        return None

async def generate_video_huggingface(prompt: str):
    """Generate video using HuggingFace API"""
    if not HUGGINGFACE_API_TOKEN:
        return None
    
    try:
        # Use HuggingFace's diffusers video generation
        API_URL = "https://api-inference.huggingface.co/models/ali-vilab/text-to-video-ms-1.7b"
        headers = {"Authorization": f"Bearer {HUGGINGFACE_API_TOKEN}"}
        
        payload = {
            "inputs": prompt,
            "parameters": {
                "num_frames": 16,
                "fps": 8,
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(API_URL, json=payload, headers=headers, timeout=120) as response:
                if response.status == 200:
                    return await response.read()
                else:
                    print(f"HuggingFace API error: {response.status}")
                    return None
    except Exception as e:
        print(f"HuggingFace video generation error: {e}")
        return None

async def generate_video_fallback(prompt: str):
    """Generate a video using free alternative (image sequence)"""
    try:
        # Generate multiple frames using Pollinations.ai
        frames = []
        for i in range(5):
            frame_prompt = f"{prompt}, frame {i+1}, smooth animation"
            url = f"https://image.pollinations.ai/prompt/{frame_prompt.replace(' ', '%20')}?width=512&height=512&nologo=true"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as response:
                    if response.status == 200:
                        frames.append(await response.read())
            await asyncio.sleep(1)
        
        if frames:
            # Create a simple animated GIF from frames
            from PIL import Image
            import io
            
            images = []
            for frame_data in frames:
                img = Image.open(io.BytesIO(frame_data))
                images.append(img)
            
            # Save as animated GIF
            output = io.BytesIO()
            images[0].save(
                output,
                format='GIF',
                save_all=True,
                append_images=images[1:],
                duration=500,
                loop=0
            )
            output.seek(0)
            return output.read()
        return None
    except Exception as e:
        print(f"Fallback video generation error: {e}")
        return None

async def generate_video(prompt: str):
    """Generate video using available API"""
    # Try Replicate first if available
    if REPLICATE_AVAILABLE:
        video = await generate_video_replicate(prompt)
        if video:
            return video, "Replicate AI"
    
    # Try HuggingFace if available
    if HUGGINGFACE_API_TOKEN:
        video = await generate_video_huggingface(prompt)
        if video:
            return video, "HuggingFace AI"
    
    # Fallback to image-to-GIF animation
    video = await generate_video_fallback(prompt)
    if video:
        return video, "AI Animation (GIF)"
    
    return None, None

def detect_video_type(prompt: str):
    """Detect what type of video to generate"""
    prompt_lower = prompt.lower()
    
    if any(word in prompt_lower for word in ['nature', 'landscape', 'sunset', 'mountain', 'forest', 'ocean', 'beach']):
        return "Nature"
    elif any(word in prompt_lower for word in ['city', 'urban', 'street', 'building', 'skyscraper', 'traffic']):
        return "Urban"
    elif any(word in prompt_lower for word in ['fantasy', 'dragon', 'castle', 'magic', 'wizard', 'elf']):
        return "Fantasy"
    elif any(word in prompt_lower for word in ['space', 'galaxy', 'planet', 'star', 'astronaut', 'universe']):
        return "Space"
    elif any(word in prompt_lower for word in ['cartoon', 'anime', 'character', 'animation', 'drawing']):
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
    
    # Check video generation status
    video_status = "✅ Replicate AI" if REPLICATE_AVAILABLE else "⚠️ Limited (GIF animation)"
    
    welcome_message = (
        f"🎬 Welcome {user.first_name} to **VidForgeBot**!\n\n"
        "Your AI video and image generation companion!\n\n"
        "**✨ Features:**\n"
        "• 🎬 Generate REAL videos from text prompts\n"
        "• 🖼️ Generate images from text descriptions\n"
        "• 🎯 Multiple video styles (Nature, Urban, Fantasy, Space, Cartoon)\n"
        "• 📋 View generation history\n\n"
        f"**⚡ Video Engine:** {video_status}\n\n"
        "**🎯 Quick Start:**\n"
        "• Click 'Generate Video' and enter a description\n"
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
        "• Get AI-generated video (3-5 seconds)\n\n"
        "**🖼️ Generate Image**\n"
        "• Click 'Generate Image'\n"
        "• Enter a description\n"
        "• Get AI-generated image\n\n"
        "**🎯 Video Styles**\n"
        "• **Nature:** Landscapes, sunsets, mountains\n"
        "• **Urban:** Cities, streets, buildings\n"
        "• **Fantasy:** Dragons, castles, magic\n"
        "• **Space:** Galaxies, planets, astronauts\n"
        "• **Cartoon:** Animated characters, scenes\n\n"
        "**⚠️ Note:**\n"
        "• Videos take 30-60 seconds to generate\n"
        "• Add REPLICATE_API_TOKEN for better quality\n\n"
        "**Commands**\n"
        "/start - Start the bot\n"
        "/help - Show this help"
    )
    
    await update.message.reply_text(
        help_text,
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

# ==================== IMAGE GENERATION ====================
async def generate_image(prompt: str, size: str = "512x512"):
    """Generate an image using Pollinations.ai"""
    try:
        clean_prompt = prompt.strip().replace(" ", "%20")
        width, height = size.split("x")
        
        url = f"https://image.pollinations.ai/prompt/{clean_prompt}?width={width}&height={height}&nologo=true&seed={int(datetime.now().timestamp())}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=30) as response:
                if response.status == 200:
                    return await response.read()
                else:
                    return None
    except Exception as e:
        print(f"Image generation error: {e}")
        return None

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
            "🎬 **Generating video...**\n\n"
            "⏳ This may take 30-60 seconds...\n"
            f"📝 Prompt: {text}",
            parse_mode="Markdown"
        )
        
        # Detect video type
        video_type = user_sessions[user_id].get("video_type", "random")
        if video_type == "random":
            video_type = detect_video_type(text)
        
        # Generate video
        video_data, engine = await generate_video(text)
        
        await processing_msg.delete()
        
        if video_data:
            # Save to history
            if user_id not in video_history:
                video_history[user_id] = []
            video_history[user_id].append({
                "timestamp": datetime.now().isoformat(),
                "prompt": text,
                "type": f"Video ({video_type})"
            })
            
            # Send video
            await update.message.reply_video(
                video=io.BytesIO(video_data),
                caption=f"🎬 **Video Generated!**\n\n"
                       f"📝 **Prompt:** {text}\n"
                       f"🎯 **Style:** {video_type.title()}\n"
                       f"⚡ **Engine:** {engine}\n\n"
                       f"💡 Click below to generate more!",
                parse_mode="Markdown",
                reply_markup=get_result_keyboard()
            )
        else:
            await update.message.reply_text(
                "❌ **Failed to generate video**\n\n"
                "Please try:\n"
                "• A different description\n"
                "• Shorter prompt (under 100 characters)\n"
                "• Waiting a few seconds and retrying\n\n"
                "💡 Tip: For better videos, add a REPLICATE_API_TOKEN",
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
                "Please try again with a different description.",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
        
        user_sessions[user_id]["action"] = None
    
    else:
        # Default response
        await update.message.reply_text(
            "👋 **Use the buttons below!**\n\n"
            "I can:\n"
            "• 🎬 Generate REAL videos from text\n"
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
    print(f"⚡ Replicate API: {'✅ Available' if REPLICATE_AVAILABLE else '❌ Not configured'}")
    print(f"⚡ HuggingFace API: {'✅ Available' if HUGGINGFACE_API_TOKEN else '❌ Not configured'}")
    print("🖼️ Ready to generate videos and images!")
    print("=" * 50)
    
    # Build application
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .connect_timeout(120.0)
        .read_timeout(120.0)
        .build()
    )
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    
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
