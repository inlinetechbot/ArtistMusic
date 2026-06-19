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
from pyrogram import filters, types
from pyrogram.errors import ChatAdminRequired, ChannelPrivate

from Elevenyts import app, config


# ==========================================
# 🟢 BOT ADDED IN GROUP
# ==========================================
@app.on_message(filters.new_chat_members & filters.group)
async def new_chat_member(_, message: types.Message):

    for member in message.new_chat_members:
        if member.id == app.id:
            chat = message.chat

            chat_name = chat.title
            chat_id = chat.id
            chat_username = f"@{chat.username}" if chat.username else "ᴘʀɪᴠᴀᴛᴇ ɢʀᴏᴜᴘ"

            try:
                members_count = await app.get_chat_members_count(chat_id)
            except (ChannelPrivate, Exception):
                members_count = "ᴜɴᴋɴᴏᴡɴ"

            added_by = message.from_user
            added_by_name = added_by.mention if added_by else "ᴜɴᴋɴᴏᴡɴ"

            # 🔗 LINK SYSTEM
            try:
                if chat.username:
                    chat_link = f"https://t.me/{chat.username}"
                else:
                    bot_member = await app.get_chat_member(chat_id, app.id)
                    if bot_member.privileges and bot_member.privileges.can_invite_users:
                        chat_link = await app.export_chat_invite_link(chat_id)
                    else:
                        chat_link = "❌ ɴᴏ ɪɴᴠɪᴛᴇ ᴘᴇʀᴍɪssɪᴏɴ"
            except ChatAdminRequired:
                chat_link = "❌ ʙᴏᴛ ɴᴏᴛ ᴀᴅᴍɪɴ"
            except Exception:
                chat_link = "❌ ᴜɴᴀʙʟᴇ ᴛᴏ ɢᴇᴛ ʟɪɴᴋ"

            text = f"""<blockquote>🟢 <b>𝐎𝗉𝗎𝗌𝐌𝗎𝗌𝗂𝖼 𝐀𝖽𝖽𝖾𝖽 𝐈𝗇 𝐀 𝐍𝖾𝗐 𝐆𝗋𝗈𝗎𝗉</b></blockquote>

<blockquote>
🔖 <b>𝐂𝗁𝖺𝗍 𝐍𝖺𝗆𝖾:</b> {chat_name}
🆔 <b>𝐂𝗁𝖺𝗍 𝐈𝖣:</b> <code>{chat_id}</code>
👤 <b>𝐂𝗁𝖺𝗍 𝐔𝗌𝖾𝗋𝗇𝖺𝗆𝖾:</b> {chat_username}
🔗 <b>𝐂𝗁𝖺𝗍 𝐋𝗂𝗇𝗄:</b> {chat_link}
👥 <b>𝐆𝗋𝗈𝗎𝗉 𝐌𝖾𝗆𝖻𝖾𝗋𝗌:</b> {members_count}
🤵 <b>𝐀𝖽𝖽𝖾𝖽 𝐁𝗒:</b> {added_by_name}
</blockquote>
"""

            try:
                await app.send_photo(
                    chat_id=config.LOGGER_ID,
                    photo=config.START_IMG,
                    caption=text
                )
            except Exception as e:
                print(f"Failed to send new chat notification: {e}")

            break


# ==========================================
# 🔴 BOT REMOVED
# ==========================================
@app.on_message(filters.left_chat_member & filters.group)
async def left_chat_member(_, message: types.Message):

    if message.left_chat_member.id == app.id:
        chat = message.chat

        chat_name = chat.title
        chat_id = chat.id
        chat_username = f"@{chat.username}" if chat.username else "ᴘʀɪᴠᴀᴛᴇ ɢʀᴏᴜᴘ"

        removed_by = message.from_user
        removed_by_name = removed_by.mention if removed_by else "ᴜɴᴋɴᴏᴡɴ"

        # 🔗 LINK
        try:
            if chat.username:
                chat_link = f"https://t.me/{chat.username}"
            else:
                bot_member = await app.get_chat_member(chat_id, app.id)
                if bot_member.privileges and bot_member.privileges.can_invite_users:
                    chat_link = await app.export_chat_invite_link(chat_id)
                else:
                    chat_link = "❌ ɴᴏ ɪɴᴠɪᴛᴇ ᴘᴇʀᴍɪssɪᴏɴ"
        except:
            chat_link = "❌ ᴜɴᴀʙʟᴇ ᴛᴏ ɢᴇᴛ ʟɪɴᴋ"

        text = f"""<blockquote><b>𝐎𝗉𝗎𝗌𝐌𝗎𝗌𝗂𝖼 𝐑𝖾𝗆𝗈𝗏𝖾𝖽 𝐅𝗋𝗈𝗆 𝐀 𝐆𝗋𝗈𝗎𝗉</b></blockquote>

<blockquote>
🔖 <b>✤ 𝐂𝗁𝖺𝗍 𝐍𝖺𝗆𝖾:</b> {chat_name}
🆔 <b>✤ 𝐂𝗁𝖺𝗍 𝐈𝖣:</b> <code>{chat_id}</code>
👤 <b>✤ 𝐂𝗁𝖺𝗍 𝐔𝗌𝖾𝗋𝗇𝖺𝗆𝖾:</b> {chat_username}
🔗 <b>✤ 𝐂𝗁𝖺𝗍 𝐋𝗂𝗇𝗄:</b> {chat_link}
🚫 <b>✤ 𝐑𝖾𝗆𝗈𝗏𝖾𝖽 𝐁𝗒:</b> {removed_by_name}
</blockquote>
"""

        try:
            await app.send_photo(
                chat_id=config.LOGGER_ID,
                photo=config.START_IMG,
                caption=text
            )
        except Exception as e:
            print(f"Failed to send left chat notification: {e}")


# ==========================================
# 🔗 /LINK COMMAND (OWNER ONLY)
# ==========================================
@app.on_message(filters.command("link") & filters.private)
async def get_group_link(_, message: types.Message):

    # OWNER CHECK
    if message.from_user.id != config.OWNER_ID:
        return await message.reply_text("❌ You are not authorized.")

    if len(message.command) < 2:
        return await message.reply_text("⚠️ Usage:\n/link <group_id>")

    try:
        chat_id = int(message.command[1])
    except:
        return await message.reply_text("❌ Invalid group ID")

    try:
        chat = await app.get_chat(chat_id)

        if chat.username:
            link = f"https://t.me/{chat.username}"
        else:
            bot_member = await app.get_chat_member(chat_id, app.id)

            if bot_member.privileges and bot_member.privileges.can_invite_users:
                link = await app.export_chat_invite_link(chat_id)
            else:
                return await message.reply_text("❌ No invite permission")

        await message.reply_text(
            f"🔗 <b>Group Link:</b>\n{link}",
            disable_web_page_preview=True
        )

    except ChannelPrivate:
        await message.reply_text("❌ Bot is not in that group")

    except ChatAdminRequired:
        await message.reply_text("❌ Bot is not admin")

    except Exception as e:
        await message.reply_text(f"❌ Error:\n{e}")
