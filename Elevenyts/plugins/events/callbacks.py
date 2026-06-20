# ==========================================================
# Copyright (c) 2026 ArtistBots
# All Rights Reserved.
#
# Project      : ArtistBots API Telegram Music Bot
# Powered By   : Artist
# Type         : API Based Telegram Music Bot
#
# Bot          : @ArtistApibot
# Channel      : https://t.me/artistbots
# GitHub       : https://github.com/elevenyts
#
# Unauthorized copying, modification, or redistribution
# of this source code without permission is prohibited.
# ==========================================================

import re
import asyncio
from functools import wraps

from pyrogram import filters, types
from pyrogram.errors import FloodWait, QueryIdInvalid

from Elevenyts import tune, app, config, db, lang, logger, queue, tg, yt
from Elevenyts.helpers import admin_check, buttons, can_manage_vc


def safe_callback(func):
    """Decorator to handle exceptions in callback handlers."""
    @wraps(func)
    async def wrapper(client, query: types.CallbackQuery):
        try:
            return await func(client, query)
        except QueryIdInvalid:
            return
        except Exception as e:
            logger.error(f"Error in callback {func.__name__}: {e}", exc_info=True)
            try:
                await query.answer("❌ An error occurred. Please try again.", show_alert=True)
            except Exception:
                pass
    return wrapper


@app.on_callback_query(filters.regex("^start$") & ~app.bl_users)
@lang.language()
@safe_callback
async def _start_callback(_, query: types.CallbackQuery):
    """Handle start button callback - return to start message."""
    await query.answer()
    
    _text = query.lang["start_pm"].format(query.from_user.first_name, app.name)
    key = buttons.start_key(query.lang, True)
    
    try:
        await query.edit_message_caption(
            caption=_text,
            reply_markup=key,
        )
    except Exception:
        try:
            await query.edit_message_text(
                text=_text,
                reply_markup=key,
            )
        except Exception:
            pass


@app.on_callback_query(filters.regex("cancel_dl") & ~app.bl_users)
@lang.language()
@safe_callback
async def cancel_dl(_, query: types.CallbackQuery):
    await query.answer()
    await tg.cancel(query)


@app.on_callback_query(filters.regex("controls") & ~app.bl_users)
@lang.language()
@safe_callback
async def _controls(_, query: types.CallbackQuery):
    args = query.data.split()
    action, chat_id = args[1], int(args[2])
    qaction = len(args) == 4
    user = query.from_user.mention

    if action == "close":
        await query.answer()
        try:
            await query.message.delete()
        except Exception:
            pass
        return

    user_id = query.from_user.id
    has_permission = False
    
    if user_id in app.sudoers:
        has_permission = True
    elif await db.is_auth(chat_id, user_id):
        has_permission = True
    else:
        admins = await db.get_admins(chat_id)
        if user_id in admins:
            has_permission = True
    
    if not has_permission:
        return await query.answer("⚠️ You don't have permission to use this.", show_alert=True)

    if not await db.get_call(chat_id):
        return await query.answer(query.lang["not_playing"], show_alert=True)

    if action == "status":
        return await query.answer()
    
    if action.startswith("seek_"):
        return await handle_seek(query, chat_id, action, user)
    
    if action == "loop":
        return await handle_loop(query, chat_id, user)
    
    if action == "shuffle":
        return await handle_shuffle(query, chat_id, user)
    
    await query.answer(query.lang["processing"], show_alert=True)

    if action == "pause":
        if not await db.playing(chat_id):
            return await query.answer(
                query.lang["play_already_paused"], show_alert=True
            )
        if not await tune.pause(chat_id):
            return await query.answer(query.lang["not_playing"], show_alert=True)
        if qaction:
            return await query.edit_message_reply_markup(
                reply_markup=buttons.queue_markup(
                    chat_id, query.lang["paused"], False)
            )
        status = query.lang["paused"]
        reply = query.lang["play_paused"].format(user)

    elif action == "resume":
        status = query.lang["playing"]
        if await db.playing(chat_id):
            return await query.answer(query.lang["play_not_paused"], show_alert=True)
        if not await tune.resume(chat_id):
            return await query.answer(query.lang["not_playing"], show_alert=True)
        if qaction:
            return await query.edit_message_reply_markup(
                reply_markup=buttons.queue_markup(
                    chat_id, query.lang["playing"], True)
            )
        reply = query.lang["play_resumed"].format(user)

    elif action == "skip":
        await tune.play_next(chat_id)
        status = query.lang["skipped"]
        reply = query.lang["play_skipped"].format(user)

    elif action == "force":
        pos, media = queue.check_item(chat_id, args[3])
        if not media or pos == -1:
            return await query.edit_message_text(query.lang["play_expired"])

        current = queue.get_current(chat_id)
        m_id = current.message_id if current else None
        queue.force_add(chat_id, media, remove=pos)
        try:
            await app.delete_messages(
                chat_id=chat_id, message_ids=[
                    m_id, media.message_id], revoke=True
            )
            media.message_id = None
        except:
            pass

        msg = await app.send_message(chat_id=chat_id, text=query.lang["play_next"])
        if not media.file_path:
            media.file_path = await yt.download(
                media.id,
                video=getattr(media, "video", False),
            )
        media.message_id = msg.id
        return await tune.play_media(chat_id, msg, media)

    elif action == "replay":
        media = queue.get_current(chat_id)
        media.user = user
        await tune.replay(chat_id)
        status = query.lang["replayed"]
        reply = query.lang["play_replayed"].format(user)

    elif action == "stop":
        await tune.stop(chat_id)
        status = query.lang["stopped"]
        reply = query.lang["play_stopped"].format(user)

    try:
        if action in ["skip", "replay", "stop"]:
            sent_msg = None
            try:
                sent_msg = await query.message.reply_text(reply, quote=False)
            except FloodWait as e:
                await asyncio.sleep(e.value)
                try:
                    sent_msg = await query.message.reply_text(reply, quote=False)
                except Exception:
                    pass
            except Exception:
                pass
            await query.message.delete()
            
            if sent_msg:
                await asyncio.sleep(5)
                try:
                    await sent_msg.delete()
                except Exception:
                    pass
        else:
            mtext = re.sub(
                r"\n\n<blockquote>.*?</blockquote>",
                "",
                query.message.caption.html or query.message.text.html,
                flags=re.DOTALL,
            )
            keyboard = buttons.controls(
                chat_id, status=status if action != "resume" else None
            )
        await query.edit_message_text(
            f"{mtext}\n\n<blockquote>{reply}</blockquote>", reply_markup=keyboard
        )
    except FloodWait as e:
        await asyncio.sleep(e.value)
        try:
            await query.edit_message_text(
                f"{mtext}\n\n<blockquote>{reply}</blockquote>", reply_markup=keyboard
            )
        except Exception:
            pass
    except Exception:
        pass


async def handle_seek(query: types.CallbackQuery, chat_id: int, action: str, user: str):
    """Handle seek forward/backward actions."""
    media = queue.get_current(chat_id)
    if not media or media.is_live:
        return await query.answer("⚠️ Cannot seek in live streams!", show_alert=True)
    
    if not media.duration_sec or media.duration_sec == 0:
        return await query.answer("⚠️ Cannot seek in this track!", show_alert=True)
    
    if action == "seek_back_10":
        seconds = -10
    elif action == "seek_back_30":
        seconds = -30
    elif action == "seek_forward_10":
        seconds = 10
    elif action == "seek_forward_30":
        seconds = 30
    else:
        return await query.answer("⚠️ Invalid seek action!", show_alert=True)
    
    current_time = getattr(media, 'time', 0)
    new_time = max(0, min(current_time + seconds, media.duration_sec - 5))
    
    if new_time == 0 and seconds < 0:
        return await query.answer(f"⏮️ Already at the beginning!", show_alert=True)
    if new_time >= media.duration_sec - 5 and seconds > 0:
        return await query.answer(f"⏭️ Too close to the end!", show_alert=True)
    
    success = await tune.seek_stream(chat_id, int(new_time))
    if success:
        import time as time_module
        if media.duration_sec >= 3600:
            time_str = time_module.strftime('%H:%M:%S', time_module.gmtime(new_time))
        else:
            time_str = time_module.strftime('%M:%S', time_module.gmtime(new_time))
        
        await query.answer(f"✅ Seeked to {time_str}", show_alert=True)
        
        try:
            sent_msg = await query.message.reply_text(
                f"✅ Seeked to {time_str}\n\n<blockquote>By {user}</blockquote>",
                quote=False
            )
            await asyncio.sleep(5)
            try:
                await sent_msg.delete()
            except Exception:
                pass
        except FloodWait:
            pass
        except Exception:
            pass


async def handle_loop(query: types.CallbackQuery, chat_id: int, user: str):
    """Handle loop mode toggling."""
    current_loop = await db.get_loop(chat_id)
    
    if current_loop == 0:
        new_loop = 1
        text = "🔂 Loop: Single Track"
        message = f"🔂 Loop mode set to <b>Single Track</b>"
    elif current_loop == 1:
        new_loop = 10
        text = "🔁 Loop: Queue"
        message = f"🔁 Loop mode set to <b>Queue</b>"
    else:
        new_loop = 0
        text = "➡️ Loop: Off"
        message = f"➡️ Loop mode <b>Disabled</b>"
    
    await db.set_loop(chat_id, new_loop)
    await query.answer(text, show_alert=False)
    await query.message.reply_text(message, quote=False)


async def handle_shuffle(query: types.CallbackQuery, chat_id: int, user: str):
    """Handle queue shuffling."""
    import random
    
    items = queue.get_queue(chat_id)
    if not items or len(items) <= 1:
        return await query.answer("⚠️ Queue is empty or has only one track!", show_alert=True)
    
    current = items[0] if items else None
    remaining = items[1:] if len(items) > 1 else []
    
    if not remaining:
        return await query.answer("⚠️ No tracks to shuffle!", show_alert=True)
    
    random.shuffle(remaining)
    
    queue.clear(chat_id)
    if current:
        queue.add(chat_id, current)
    for item in remaining:
        queue.add(chat_id, item)
    
    await query.answer("🔀 Queue shuffled!", show_alert=False)
    await query.message.reply_text(
        f"🔀 Queue <b>shuffled</b> ({len(remaining)} tracks)",
        quote=False
    )


@app.on_callback_query(filters.regex(r"^help") & ~app.bl_users)
@lang.language()
async def _help(_, query: types.CallbackQuery):
    await query.answer()
    
    if query.data == "help":
        try:
            await query.edit_message_caption(
                caption=query.lang["help_menu"], 
                reply_markup=buttons.help_markup(query.lang)
            )
        except Exception:
            try:
                await query.edit_message_text(
                    text=query.lang["help_menu"], 
                    reply_markup=buttons.help_markup(query.lang)
                )
            except Exception:
                pass
        return
    
    category = query.data.replace("help_", "")
    
    if category == "main":
        try:
            await query.edit_message_caption(
                caption=query.lang["help_menu"], 
                reply_markup=buttons.help_markup(query.lang)
            )
        except Exception:
            try:
                await query.edit_message_text(
                    text=query.lang["help_menu"], 
                    reply_markup=buttons.help_markup(query.lang)
                )
            except Exception:
                pass
        return

    help_texts = {
        "admins": query.lang["help_admins"],
        "auth": query.lang["help_auth"],
        "broadcast": query.lang["help_sudo"],
        "blchat": query.lang["help_blchat"],
        "bluser": query.lang["help_bluser"],
        "gban": query.lang["help_gban"],
        "loop": query.lang["help_loop"],
        "play": query.lang["help_play"],
        "queue": query.lang["help_queue"],
        "seek": query.lang["help_seek"],
        "shuffle": query.lang["help_shuffle"],
        "ping": query.lang["help_ping"],
        "stats": query.lang["help_stats"],
        "sudo": query.lang["help_sudo"],
        "maintenance": query.lang["help_maintenance"],
    }
    
    help_text = help_texts.get(category, query.lang["help_admins"])
    
    try:
        await query.edit_message_caption(
            caption=help_text,
            reply_markup=buttons.help_markup(query.lang, True),
        )
    except Exception:
        try:
            await query.edit_message_text(
                text=help_text,
                reply_markup=buttons.help_markup(query.lang, True),
            )
        except Exception:
            pass


@app.on_callback_query(filters.regex("playmode") & ~app.bl_users)
@lang.language()
@admin_check
async def _playmode(_, query: types.CallbackQuery):
    await query.answer(query.lang["processing"], show_alert=True)
    chat_id = query.message.chat.id
    admin_only = await db.get_play_mode(chat_id)
    _language = "en"
    await db.set_play_mode(chat_id, admin_only)
    await query.edit_message_reply_markup(
        reply_markup=buttons.settings_markup(
            query.lang,
            not admin_only,
            _language,
            chat_id,
        )
    )


# ── Info Menu Callbacks ────────────────────────────────────
@app.on_callback_query(filters.regex("^info_menu$") & ~app.bl_users)
@lang.language()
@safe_callback
async def _info_menu(_, query: types.CallbackQuery):
    """Show info submenu when ɪɴꜰᴏ button is tapped."""
    await query.answer()
    try:
        await query.edit_message_caption(
            caption=query.lang.get("info_menu", " <b>𝙄𝙣𝙛𝙤𝙈𝙚𝙣𝙪 \n\n𝐎𝗉𝗎𝗌𝐌𝗎𝗌𝗂𝖼™ \n <blockquote> 𝐈𝗌 𝐀 𝐏𝗈𝗐𝖾𝗋𝖿𝗎𝗅 𝐓𝖾𝗅𝖾𝗀𝗋𝖺𝗆 𝐌𝗎𝗌𝗂𝖼 𝐁𝗈𝗍 𝐃𝖾𝗌𝗂𝗀𝗇𝖾𝖽 𝐓𝗈 𝐃𝖾𝗅𝗂𝗏𝖾𝗋 𝐇𝗂𝗀𝗁-𝐐𝗎𝖺𝗅𝗂𝗍𝗒 𝐀𝗎𝖽𝗂𝗈 𝐒𝗍𝗋𝖾𝖺𝗆𝗂𝗇𝗀 𝐃𝗂𝗋𝖾𝖼𝗍𝗅𝗒 𝐈𝗇 𝐕𝗈𝗂𝖼𝖾 𝐂𝗁𝖺𝗍.</blockquote>\n<blockquote>𝐒𝖾𝗅𝖾𝖼𝗍 𝐀𝗇 𝐎𝗉𝗍𝗂𝗈𝗇 𝐁𝖾𝗅𝗈𝗐 𝐓𝗈 𝐋𝖾𝖺𝗋𝗇 𝐌𝗈𝗋𝖾 𝐀𝖻𝗈𝗎𝗍 𝐓𝗁𝖾 𝐁𝗈𝗍, 𝐎𝗐𝗇𝖾𝗋 𝐃𝖾𝗏𝖾𝗅𝗈𝗉𝖾𝗋 𝐀𝗏𝖺𝗂𝗅𝖺𝖻𝗅𝖾 𝐅𝖾𝖺𝗍𝗎𝗋𝖾.</blockquote></b>"),
            reply_markup=buttons.info_markup(),
        )
    except Exception:
        try:
            await query.edit_message_text(
                text=query.lang.get("info_menu", " <b>𝐒𝗁𝗈𝗐𝗌 𝐃𝖾𝗍𝖺𝗂𝗅𝗌 𝐀𝗇𝖽 𝐇𝖾𝗅𝗉𝖿𝗎𝗅 𝐈𝗇𝖿𝗈𝗋𝗆𝖺𝗍𝗂𝗈𝗇 𝐀𝖻𝗈𝗎𝗍 𝐓𝗁𝗂𝗌 𝐎𝗉𝗍𝗂𝗈𝗇𝗌.</b>"),
                reply_markup=buttons.info_markup(),
            )
        except Exception:
            pass


@app.on_callback_query(filters.regex("^info_close$") & ~app.bl_users)
@safe_callback
async def _info_close(_, query: types.CallbackQuery):
    """Close the message when ᴄʟᴏꜱᴇ button is tapped."""
    await query.answer()
    try:
        await query.message.delete()
    except Exception:
        pass
