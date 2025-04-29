import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from dotenv import load_dotenv
from collections import defaultdict
import asyncio
import aiohttp
import random
import re
import datetime
import json
from typing import Any

# Load environment variables from .env file
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
VYBE_API_KEY = os.getenv('VYBE_API_KEY')

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not set in environment variables.")
if not VYBE_API_KEY:
    raise ValueError("VYBE_API_KEY not set in environment variables.")

API_BASE = "https://api.vybenetwork.xyz/v1"

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# New state structure
user_states = defaultdict(lambda: {"step": "idle", "temp": {}})  # step: awaiting_wallet_address, awaiting_nickname, awaiting_token_info, awaiting_token_price, idle
saved_wallets = defaultdict(list)  # user_id -> [{"address": ..., "nickname": ...}]

# Helper for Solana wallet validation
BASE58_REGEX = re.compile(r'^[A-HJ-NP-Za-km-z1-9]{32,44}$')
def is_valid_wallet_address(addr):
    return bool(BASE58_REGEX.fullmatch(addr))

# List of elegant loading messages
LOADING_MESSAGES = [
    "⏳ Fetching data from the blockchain...",
    "⏳ Querying the Vybe Network API...",
    "⏳ Processing your request...",
    "⏳ Almost there...",
    "⏳ Compiling information..."
]

# List of subtle Solana/Crypto facts/tips
SOLANA_TIPS = [
    "Did you know? Solana uses a unique consensus mechanism called Proof of History (PoH).",
    "Tip: Solana wallet addresses are typically 44 characters long and base58 encoded.",
    "Fact: SPL is the token standard on the Solana blockchain, similar to ERC-20 on Ethereum.",
    "Did you know? Solana is known for its high transaction speed and low fees.",
    "Tip: Always double-check the address before sending tokens!"
]

# --- Keyboards ---
def main_menu_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💼 Wallet Management", callback_data="wallet_menu")],
            [InlineKeyboardButton(text="🪙 Token Tools", callback_data="token_menu")],
            [InlineKeyboardButton(text="🎬 Demo", callback_data="demo")],
            [InlineKeyboardButton(text="👋 End Chat", callback_data="end_chat")],
        ]
    )

def wallet_management_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Save Wallet", callback_data="save_wallet")],
            [InlineKeyboardButton(text="⭐ My Wallets", callback_data="my_wallets")],
            [InlineKeyboardButton(text="🏠 Back to Main Menu", callback_data="main_menu")],
        ]
    )

def token_tools_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🪙 Token Details", callback_data="token_details")],
            [InlineKeyboardButton(text="🔄 Token Transfers", callback_data="token_transfers")],
            [InlineKeyboardButton(text="📝 Instruction Names", callback_data="instruction_names")],
            [InlineKeyboardButton(text="🏠 Back to Main Menu", callback_data="main_menu")],
        ]
    )

# NEW Keyboard for options after saving or selecting a wallet
def wallet_options_keyboard(wallet_idx: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 View Holdings", callback_data=f"view_holdings_{wallet_idx}")],
            [InlineKeyboardButton(text="🔄 Recent Transfers", callback_data=f"recent_transfers_{wallet_idx}")],
            [InlineKeyboardButton(text="🔔 Set Alert", callback_data=f"alert_{wallet_idx}")],
            [InlineKeyboardButton(text="🗑️ Delete Wallet", callback_data=f"delete_{wallet_idx}")],
            [InlineKeyboardButton(text="🏠 Back to Main Menu", callback_data="main_menu")],
        ]
    )

# Keyboard for displaying the list of saved wallets
def my_wallets_keyboard(user_id):
    wallets = saved_wallets.get(user_id, [])
    rows = []
    if not wallets:
        rows.append([InlineKeyboardButton(text="➕ Save Wallet First", callback_data="save_wallet")])
    else:
        for idx, w in enumerate(wallets):
            preview = w["address"][:5] + "..." + w["address"][-5:]
            label = f"{w['nickname']} ({preview})"
            # Button now triggers selecting the wallet to show options
            rows.append([InlineKeyboardButton(text=label, callback_data=f"select_wallet_{idx}")])
    
    rows.append([InlineKeyboardButton(text="🏠 Back to Main Menu", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def show_more_keyboard(context_key):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Show More", callback_data=f"show_more_{context_key}")],
            [InlineKeyboardButton(text="Back", callback_data="token_menu")]
        ]
    )

# --- Commands ---
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_states[message.from_user.id] = {"step": "idle", "temp": {}}
    random_tip = random.choice(SOLANA_TIPS)
    welcome_msg = (
        "👋 <b>Welcome to WhaleVybe!</b>\n\n"
        "Your elegant companion for tracking Solana wallets and exploring token information.\n\n"
        f"<i>{random_tip}</i>\n\n"
        "Choose an option below to get started:"
    )
    await message.answer(
        welcome_msg,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard() # Start with the main menu
    )

@dp.message(Command("cancel"))
async def cmd_cancel(message: Message):
    user_id = message.from_user.id
    current_step = user_states[user_id]["step"]
    user_states[user_id] = {"step": "idle", "temp": {}}
    msg = "<i>Action cancelled.</i>"
    reply_markup = main_menu_keyboard()
    
    # Determine which menu to return to based on the cancelled step
    if current_step in ["awaiting_wallet_address", "awaiting_nickname"]:
        msg += " Back to Wallet Management."
        reply_markup = wallet_management_keyboard()
    elif current_step in ["awaiting_token_details", "awaiting_token_transfers"]:
        msg += " Back to Token Tools."
        reply_markup = token_tools_keyboard()
    else:
        msg += " Back to Main Menu."

    await message.answer(msg, parse_mode="HTML", reply_markup=reply_markup)

@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Save a wallet ➔ Give it a nickname ➔ Track activity, set alerts, check token info easily. Use the menu below to navigate.",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard()
    )

# --- Main menu callback handler ---
@dp.callback_query(lambda c: c.data == "main_menu")
async def process_main_menu(callback_query: CallbackQuery):
    user_states[callback_query.from_user.id] = {"step": "idle", "temp": {}}
    await callback_query.answer()
    await callback_query.message.edit_text( # Use edit_text for smoother navigation
        "<b>🏠 Main Menu</b>\nChoose an option:",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard()
    )

@dp.callback_query(lambda c: c.data == "wallet_menu")
async def process_wallet_management_menu(callback_query: CallbackQuery):
    await callback_query.answer()
    await callback_query.message.edit_text(
        "<b>💼 Wallet Management</b>\nManage your saved Solana wallets.",
        parse_mode="HTML",
        reply_markup=wallet_management_keyboard()
    )

@dp.callback_query(lambda c: c.data == "token_menu")
async def process_token_tools_menu(callback_query: CallbackQuery):
    await callback_query.answer()
    await callback_query.message.edit_text(
        "<b>🪙 Token Tools</b>\nExplore Solana token details and transfers.",
        parse_mode="HTML",
        reply_markup=token_tools_keyboard()
    )

@dp.callback_query(lambda c: c.data == "save_wallet")
async def process_save_wallet_start(callback_query: CallbackQuery): # Renamed slightly
    user_states[callback_query.from_user.id] = {"step": "awaiting_wallet_address", "temp": {}}
    await callback_query.answer()
    await callback_query.message.edit_text( # Edit previous message
        "<b>Step 1:</b> Please enter the wallet address you want to save.",
        parse_mode="HTML"
    )

@dp.callback_query(lambda c: c.data == "my_wallets")
async def process_my_wallets(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    wallets = saved_wallets.get(user_id, [])
    await callback_query.answer()
    try:
        if not wallets:
            message_text = "📭 You haven't saved any wallets yet."
        else:
            lines = ["⭐ <b>Your Saved Wallets:</b>", "<i>Select a wallet to view options:</i>"]
            for idx, w in enumerate(wallets[:5], 1):
                preview = w["address"][:5] + "..." + w["address"][-5:]
                lines.append(f"<b>{idx}.</b> <b>{w['nickname']}</b> (<code>{preview}</code>)")
            if len(wallets) > 5:
                lines.append(f"<i>...and {len(wallets) - 5} more wallets</i>")
            message_text = "\n".join(lines)
        await callback_query.message.edit_text(
            message_text,
            parse_mode="HTML",
            reply_markup=my_wallets_keyboard(user_id)
        )
    except Exception as e:
        formatted_data = format_raw_data(wallets, max_chars=1000, max_items=3)
        await callback_query.message.edit_text(
            f"<b>⭐ Saved Wallets (Formatted):</b>\n<pre>{formatted_data}</pre>",
            parse_mode="HTML",
            reply_markup=my_wallets_keyboard(user_id)
        )

# NEW handler for when a user selects a wallet from the list
@dp.callback_query(lambda c: re.match(r"select_wallet_\d+", c.data))
async def process_select_wallet(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    match = re.match(r"select_wallet_(\d+)", callback_query.data)
    idx = int(match.group(1)) if match else None
    wallets = saved_wallets.get(user_id, [])

    if idx is None or idx >= len(wallets):
        await callback_query.answer("Error: Wallet not found.", show_alert=True)
        await callback_query.message.edit_text("Wallet not found. Please try again.", reply_markup=wallet_management_keyboard())
        return

    wallet = wallets[idx]
    nickname = wallet['nickname']
    preview = wallet["address"][:5] + "..." + wallet["address"][-5:]
    
    await callback_query.answer()
    await callback_query.message.edit_text(
        f"Selected: <b>{nickname}</b> (<code>{preview}</code>)\nWhat would you like to do?",
        parse_mode="HTML",
        reply_markup=wallet_options_keyboard(idx) # Show options for this specific wallet
    )

# --- Token Handlers (Adjust back buttons) ---
# Token Details button press
@dp.callback_query(lambda c: c.data == "token_details")
async def process_token_details_start(callback_query: CallbackQuery):
    user_states[callback_query.from_user.id] = {"step": "awaiting_token_details", "temp": {}}
    await callback_query.answer()
    await callback_query.message.edit_text(
        "<b>Enter the token mint address to get details.</b>",
        parse_mode="HTML"
    )

# Token Transfers button press
@dp.callback_query(lambda c: c.data == "token_transfers")
async def process_token_transfers_start(callback_query: CallbackQuery):
    user_states[callback_query.from_user.id] = {"step": "awaiting_token_transfers", "temp": {}}
    await callback_query.answer()
    await callback_query.message.edit_text(
        "<b>Enter a wallet address or token mint address to view transfers.</b>",
        parse_mode="HTML"
    )

# Instruction Names button press
@dp.callback_query(lambda c: c.data == "instruction_names")
async def process_instruction_names(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    await callback_query.answer()
    wait_msg = await callback_query.message.edit_text(random.choice(LOADING_MESSAGES), parse_mode="HTML")
    try:
        instruction_names = await fetch_instruction_names()
        print(f"[LOG] Instruction names response: {instruction_names}")
        if instruction_names:
            if isinstance(instruction_names, list) and instruction_names:
                chunk_size = 5
                chunks = [instruction_names[i:i + chunk_size] for i in range(0, min(len(instruction_names), 50), chunk_size)]
                lines = ["<b>📝 Solana Instruction Names:</b>"]
                for chunk in chunks:
                    formatted_chunk = [f"<code>{name}</code>" for name in chunk]
                    lines.append(" • ".join(formatted_chunk))
                if len(instruction_names) > 50:
                    lines.append(f"\n<i>...and {len(instruction_names) - 50} more instruction names</i>")
                await wait_msg.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=token_tools_keyboard())
            else:
                # Paginate raw data display
                user_states[user_id]["temp"]["raw_data_instruction_names"] = instruction_names
                user_states[user_id]["temp"]["raw_data_page_instruction_names"] = 0
                formatted_data = format_raw_data(instruction_names, max_chars=1000, max_items=3)
                await wait_msg.edit_text(
                    f"<b>📝 Instruction Names (Formatted):</b>\n<pre>{formatted_data}</pre>",
                    parse_mode="HTML",
                    reply_markup=show_more_keyboard("instruction_names")
                )
        else:
            await wait_msg.edit_text(
                "😕 I couldn't find any instruction names. The API returned an empty response.",
                parse_mode="HTML",
                reply_markup=token_tools_keyboard()
            )
    except Exception as e:
        print(f"[LOG] Exception in instruction names handler: {e}")
        await wait_msg.edit_text(
            f"🙁 I'm sorry, but I encountered an error while fetching instruction names:\n\n<i>{str(e)}</i>",
            parse_mode="HTML",
            reply_markup=token_tools_keyboard()
        )

@dp.callback_query(lambda c: c.data == "show_more_instruction_names")
async def process_show_more_instruction_names(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    temp = user_states[user_id]["temp"]
    raw_data = temp.get("raw_data_instruction_names")
    page = temp.get("raw_data_page_instruction_names", 0) + 1
    temp["raw_data_page_instruction_names"] = page
    # Increase limits for each page
    max_chars = 1000 * (page + 1)
    max_items = 3 * (page + 1)
    if raw_data:
        formatted_data = format_raw_data(raw_data, max_chars=max_chars, max_items=max_items)
        # If still truncated, keep the button, else show only Back
        reply_markup = show_more_keyboard("instruction_names") if (isinstance(raw_data, (list, dict)) and (len(str(raw_data)) > max_chars or (isinstance(raw_data, list) and len(raw_data) > max_items))) else token_tools_keyboard()
        await callback_query.message.edit_text(
            f"<b>📝 Instruction Names (More):</b>\n<pre>{formatted_data}</pre>",
            parse_mode="HTML",
            reply_markup=reply_markup
        )
    else:
        await callback_query.message.edit_text(
            "No more data to show.",
            parse_mode="HTML",
            reply_markup=token_tools_keyboard()
        )
    await callback_query.answer()

# --- Demo Handler ---
@dp.callback_query(lambda c: c.data == "demo")
async def process_demo(callback_query: CallbackQuery):
    await callback_query.answer()
    demo_msg = (
        "🎬 <b>WhaleVybe Demo & How-To:</b>\n\n"
        "1️⃣ Use <b>Wallet Management</b> to save and view your Solana wallets.\n"
        "   - Save a wallet with a nickname.\n"
        "   - Select a saved wallet to view options like Holdings or Transfers.\n\n"
        "2️⃣ Use <b>Token Tools</b> to explore Solana tokens.\n"
        "   - Get details for any token mint address.\n"
        "   - View recent transfers for a token or wallet.\n"
        "   - See a list of common instruction names.\n\n"
        "3️⃣ Use <b>End Chat</b> when you're finished.\n\n"
        "<i>Tip: Use /cancel anytime to stop the current action.</i>"
    )
    await callback_query.message.edit_text(
        demo_msg, 
        parse_mode="HTML", 
        reply_markup=main_menu_keyboard() # Back to main menu
    )

# --- Wallet Option Handlers (NEW or MODIFIED) ---

# View Holdings (Triggered from wallet_options_keyboard)
@dp.callback_query(lambda c: re.match(r"view_holdings_\d+", c.data))
async def process_view_holdings_wallet_idx(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    match = re.match(r"view_holdings_(\d+)", callback_query.data)
    idx = int(match.group(1)) if match else None
    wallets = saved_wallets.get(user_id, [])
    
    if idx is None or idx >= len(wallets):
        await callback_query.answer("Error: Wallet not found.", show_alert=True)
        # Go back to wallet management menu if wallet index is invalid
        await callback_query.message.edit_text("Wallet not found. Please try again.", reply_markup=wallet_management_keyboard()) 
        return
        
    wallet = wallets[idx]
    nickname = wallet['nickname']
    address = wallet['address']
    preview = address[:5] + "..." + address[-5:]
    
    if not is_valid_wallet_address(address):
        await callback_query.answer("Error: Invalid wallet address stored.", show_alert=True)
        await callback_query.message.edit_text(f"The stored address for {nickname} seems invalid.", reply_markup=wallet_options_keyboard(idx))
        return
        
    wait_msg = await callback_query.message.edit_text(random.choice(LOADING_MESSAGES), parse_mode="HTML") # Edit previous msg
    
    try:
        data = await fetch_wallet_holdings(address)
        if data and isinstance(data, list):
            lines = [f"📊 <b>Wallet Holdings for {nickname}</b> (<code>{preview}</code>)\n"]
            for i, token in enumerate(data[:5], 1):
                symbol = token.get("symbol", "?")
                amount = token.get("amount", "?")
                value = token.get("value", "?")
                mint = token.get("mintAddress", "?")
                lines.append(f"<b>{i}.</b> <b>{symbol}</b> | <b>Amount:</b> {amount} | <b>Value:</b> ${value} | <b>Mint:</b> <code>{short_addr(mint)}</code>")
            if len(data) > 5:
                lines.append(f"<i>...and {len(data) - 5} more tokens</i>")
            await wait_msg.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=wallet_options_keyboard(idx))
        elif data:
            formatted_data = format_raw_data(data, max_chars=1000, max_items=3)
            await wait_msg.edit_text(
                f"<b>📊 Wallet Holdings (Formatted):</b>\n<pre>{formatted_data}</pre>",
                parse_mode="HTML",
                reply_markup=wallet_options_keyboard(idx)
            )
        else:
            await wait_msg.edit_text(f"😕 Couldn't fetch holdings for <b>{nickname}</b> (<code>{preview}</code>).", parse_mode="HTML", reply_markup=wallet_options_keyboard(idx))
    except Exception as e:
        formatted_error = format_raw_data({"error": str(e)}, max_chars=1000)
        await wait_msg.edit_text(f"🙁 Error fetching holdings for <b>{nickname}</b>:\n<pre>{formatted_error}</pre>", parse_mode="HTML", reply_markup=wallet_options_keyboard(idx))

# Recent Transfers (Triggered from wallet_options_keyboard)
@dp.callback_query(lambda c: re.match(r"recent_transfers_\d+", c.data))
async def process_recent_transfers_wallet_idx(callback_query: CallbackQuery):
    print(f"[LOG] recent_transfers_idx triggered: {callback_query.data}")
    user_id = callback_query.from_user.id
    match = re.match(r"recent_transfers_(\d+)", callback_query.data)
    idx = int(match.group(1)) if match else None
    wallets = saved_wallets.get(user_id, [])

    if idx is None or idx >= len(wallets):
        await callback_query.answer("Error: Wallet not found.", show_alert=True)
        await callback_query.message.edit_text("Wallet not found. Please try again.", reply_markup=wallet_management_keyboard())
        return

    wallet = wallets[idx]
    nickname = wallet['nickname']
    address = wallet['address']
    preview = address[:5] + "..." + address[-5:]

    wait_msg = await callback_query.message.edit_text(random.choice(LOADING_MESSAGES), parse_mode="HTML")
    
    try:
        # Use the existing fetch_token_transfers which accepts wallet addresses
        transfers = await fetch_token_transfers(address)
        print(f"[LOG] Recent transfers for wallet response: {transfers}")

        if transfers and isinstance(transfers, list) and transfers:
            # Format transfers nicely
            lines = [f"🔄 <b>Recent Transfers for {nickname}</b> (<code>{preview}</code>)"]
            lines.append("") 
            
            for i, t in enumerate(transfers[:5], 1):
                # ... (Same formatting as in handle_user_input) ...
                mint = t.get("mintAddress", "Unknown Token")
                amount = t.get("amount", "?")
                sender = t.get("senderAddress", "?")
                receiver = t.get("receiverAddress", "?")
                time = t.get("blockTime", "?")
                instruction = t.get("instructionName", "Transfer")
                try:
                    formatted_time = format_time(time) if isinstance(time, (int, float)) else time
                except:
                    formatted_time = time
                lines.append(f"<b>📤 Transfer #{i}</b>")
                lines.append(f"<b>Token:</b> <code>{short_addr(mint)}</code>")
                lines.append(f"<b>Amount:</b> {amount}")
                lines.append(f"<b>From:</b> <code>{short_addr(sender)}</code>")
                lines.append(f"<b>To:</b> <code>{short_addr(receiver)}</code>")
                lines.append(f"<b>Time:</b> {formatted_time}")
                if instruction and instruction != "Transfer":
                    lines.append(f"<b>Type:</b> {instruction}")
                lines.append("")
            
            if len(transfers) > 5:
                lines.append(f"<i>...and {len(transfers) - 5} more transfers</i>")
            
            await wait_msg.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=wallet_options_keyboard(idx))
        elif transfers:
            formatted_data = format_raw_data(transfers, max_chars=1000, max_items=3)
            await wait_msg.edit_text(
                f"<b>🔄 Recent Transfers (Formatted):</b>\n<pre>{formatted_data}</pre>",
                parse_mode="HTML",
                reply_markup=wallet_options_keyboard(idx)
            )
        else:
            await wait_msg.edit_text(
                f"😕 No recent transfers found for <b>{nickname}</b> (<code>{preview}</code>).",
                parse_mode="HTML",
                reply_markup=wallet_options_keyboard(idx)
            )

    except Exception as e:
        formatted_error = format_raw_data({"error": str(e)}, max_chars=1000)
        await wait_msg.edit_text(
             f"🙁 Error fetching transfers for <b>{nickname}</b>:\n<pre>{formatted_error}</pre>", 
             parse_mode="HTML", 
             reply_markup=wallet_options_keyboard(idx)
        )

# Set Alert (Triggered from wallet_options_keyboard)
@dp.callback_query(lambda c: re.match(r"alert_\d+", c.data))
async def process_alert_wallet_idx(callback_query: CallbackQuery):
    print(f"[LOG] alert_idx triggered: {callback_query.data}")
    user_id = callback_query.from_user.id
    match = re.match(r"alert_(\d+)", callback_query.data)
    idx = int(match.group(1)) if match else None
    wallets = saved_wallets.get(user_id, [])
    
    if idx is None or idx >= len(wallets):
        await callback_query.answer("Error: Wallet not found.", show_alert=True)
        await callback_query.message.edit_text("Wallet not found. Please try again.", reply_markup=wallet_management_keyboard())
        return
        
    wallet = wallets[idx]
    nickname = wallet['nickname']
    preview = wallet["address"][:5] + "..." + wallet["address"][-5:]
    
    await callback_query.answer("Alerts (Demo)", show_alert=True)
    await callback_query.message.edit_text(
        f"🔔 Alerts feature for <b>{nickname}</b> (<code>{preview}</code>) is currently in demo mode.\nActual alert functionality is not yet implemented.",
        parse_mode="HTML",
        reply_markup=wallet_options_keyboard(idx) # Return to options for this wallet
    )

# Delete Wallet (Triggered from wallet_options_keyboard)
# Consider adding a confirmation step here in a real application
@dp.callback_query(lambda c: re.match(r"delete_\d+", c.data))
async def process_delete_wallet_idx(callback_query: CallbackQuery):
    print(f"[LOG] delete_idx triggered: {callback_query.data}")
    user_id = callback_query.from_user.id
    match = re.match(r"delete_(\d+)", callback_query.data)
    idx = int(match.group(1)) if match else None
    wallets = saved_wallets.get(user_id, [])
    
    if idx is None or idx >= len(wallets):
        await callback_query.answer("Error: Wallet not found.", show_alert=True)
        await callback_query.message.edit_text("Wallet not found. Please try again.", reply_markup=wallet_management_keyboard())
        return
        
    wallet = wallets.pop(idx) # Remove the wallet at the specified index
    nickname = wallet['nickname']
    await callback_query.answer(f"Deleted {nickname}")
    await callback_query.message.edit_text(
        f"🗑️ Wallet <b>{nickname}</b> deleted successfully.",
        parse_mode="HTML",
        reply_markup=wallet_management_keyboard() # Go back to the wallet management menu
    )

# --- Message Handler for User Input ---
@dp.message()
async def handle_user_input(message: Message):
    user_id = message.from_user.id
    state = user_states[user_id]["step"]
    temp = user_states[user_id]["temp"]

    # Save Wallet Step 1: Awaiting wallet address
    if state == "awaiting_wallet_address":
        address = message.text.strip().replace(" ", "")
        if not is_valid_wallet_address(address):
            await message.answer(
                "⚠️ Invalid wallet address. Please try again or /cancel.",
                parse_mode="HTML"
                # No keyboard change, let them retry or cancel
            )
            # user_states[user_id] = {"step": "idle", "temp": {}} # Don't reset state yet
            return
        temp["address"] = address
        user_states[user_id]["step"] = "awaiting_nickname"
        await message.answer(
            "<b>Step 2:</b> Enter a nickname for this wallet (or /cancel).",
            parse_mode="HTML"
        )
        return

    # Save Wallet Step 2: Awaiting nickname
    if state == "awaiting_nickname":
        nickname = message.text.strip()
        address = temp.get("address")
        if not nickname:
            await message.answer(
                "⚠️ Please enter a valid nickname (or /cancel).",
                parse_mode="HTML"
            )
            # user_states[user_id] = {"step": "idle", "temp": {}} # Don't reset state yet
            return
            
        if not address: # Should not happen, but safety check
             await message.answer("Error: Wallet address missing. Please /start again.", reply_markup=main_menu_keyboard())
             user_states[user_id] = {"step": "idle", "temp": {}}
             return
             
        # Check if wallet address already exists for this user
        for w in saved_wallets[user_id]:
            if w["address"] == address:
                await message.answer(
                    f"ℹ️ This wallet address is already saved as <b>{w['nickname']}</b>.",
                    parse_mode="HTML",
                    reply_markup=wallet_management_keyboard() # Back to wallet menu
                )
                user_states[user_id] = {"step": "idle", "temp": {}}
                return
                
        saved_wallets[user_id].append({"address": address, "nickname": nickname})
        new_wallet_index = len(saved_wallets[user_id]) - 1 # Get index of the newly added wallet
        preview = address[:5] + "..." + address[-5:]
        
        user_states[user_id] = {"step": "idle", "temp": {}} # Clear state after successful save
        await message.answer(
            f"✅ Saved: <b>{nickname}</b> (<code>{preview}</code>)\n\nWhat would you like to do with this wallet?",
            parse_mode="HTML",
            reply_markup=wallet_options_keyboard(new_wallet_index) # Show options for the NEWLY saved wallet
        )
        return

    # Token Details handler (Input received)
    if state == "awaiting_token_details":
        mint_address = message.text.strip()
        if len(mint_address) < 20 or not mint_address.isalnum():
            await message.answer(
                "⚠️ That doesn't look like a valid token mint address. Please try again or /cancel.",
                parse_mode="HTML"
            )
            return # Let user retry or cancel
        
        wait_msg = await message.answer(random.choice(LOADING_MESSAGES), parse_mode="HTML")
        user_states[user_id] = {"step": "idle", "temp": {}} # Clear state before processing
        
        try:
            token_details = await fetch_token_details(mint_address)
            if token_details and isinstance(token_details, dict) and not token_details.get("error") and token_details.get("name"):
                lines = [f"🪙 <b>Token Details</b>"]
                lines.append(f"<b>Address:</b> <code>{mint_address}</code>")
                token_name = token_details.get("name", "Unknown")
                token_symbol = token_details.get("symbol", "")
                lines.append(f"<b>Token:</b> {token_name} {f'({token_symbol})' if token_symbol else ''}")
                supply_info = []
                if "supply" in token_details:
                    supply_info.append(f"<b>Supply:</b> {token_details['supply']}")
                if "decimals" in token_details:
                    supply_info.append(f"<b>Decimals:</b> {token_details['decimals']}")
                if supply_info:
                    lines.append("\n<b>📊 Supply Information:</b>")
                    lines.extend(supply_info)
                authority_info = []
                if "mintAuthority" in token_details:
                    authority_info.append(f"<b>Mint Authority:</b> <code>{short_addr(token_details['mintAuthority'])}</code>")
                if "freezeAuthority" in token_details:
                    authority_info.append(f"<b>Freeze Authority:</b> <code>{short_addr(token_details['freezeAuthority'])}</code>")
                if authority_info:
                    lines.append("\n<b>🔑 Authority Information:</b>")
                    lines.extend(authority_info)
                metadata_info = []
                if "isNft" in token_details:
                    is_nft = "Yes" if token_details["isNft"] else "No"
                    metadata_info.append(f"<b>Is NFT:</b> {is_nft}")
                if "lastUpdatedAt" in token_details:
                    metadata_info.append(f"<b>Last Updated:</b> {token_details['lastUpdatedAt']}")
                if metadata_info:
                    lines.append("\n<b>ℹ️ Additional Metadata:</b>")
                    lines.extend(metadata_info)
                other_fields = []
                excluded_fields = ["name", "symbol", "supply", "decimals", "freezeAuthority", "mintAuthority", "isNft", "lastUpdatedAt", "address"]
                for key, value in token_details.items():
                    if key not in excluded_fields:
                        if isinstance(value, (str, int, float, bool)) and value:
                            other_fields.append(f"<b>{key.capitalize()}:</b> {value}")
                if other_fields:
                    lines.append("\n<b>📋 Other Information:</b>")
                    lines.extend(other_fields[:5])
                    if len(other_fields) > 5:
                        lines.append(f"<i>...and {len(other_fields) - 5} more fields</i>")
                await wait_msg.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=token_tools_keyboard())
            elif token_details:
                formatted_data = format_raw_data(token_details, max_chars=1000, max_items=3)
                await wait_msg.edit_text(
                    f"<b>🪙 Token Details (Formatted):</b>\n<pre>{formatted_data}</pre>",
                    parse_mode="HTML",
                    reply_markup=token_tools_keyboard()
                )
            else:
                await wait_msg.edit_text("😕 I couldn't find any details for this token. The token may not exist or hasn't been indexed yet.", parse_mode="HTML", reply_markup=token_tools_keyboard())
        except Exception as e:
            formatted_error = format_raw_data({"error": str(e)}, max_chars=1000)
            await wait_msg.edit_text(
                f"🙁 Error fetching token details:\n<pre>{formatted_error}</pre>",
                parse_mode="HTML",
                reply_markup=token_tools_keyboard()
            )
        
        user_states[user_id] = {"step": "idle", "temp": {}}
        return

    # Token Transfers handler (Input received)
    if state == "awaiting_token_transfers":
        address = message.text.strip()
        if len(address) < 20 or not address.isalnum():
            await message.answer(
                "⚠️ That doesn't look like a valid address. Please try again or /cancel.",
                parse_mode="HTML"
            )
            return # Let user retry or cancel
        
        wait_msg = await message.answer(random.choice(LOADING_MESSAGES), parse_mode="HTML")
        user_states[user_id] = {"step": "idle", "temp": {}} # Clear state before processing
        
        try:
            transfers = await fetch_token_transfers(address)
            if isinstance(transfers, dict) and "transfers" in transfers:
                transfers_list = transfers["transfers"]
            else:
                transfers_list = transfers if isinstance(transfers, list) else []

            if transfers_list:
                lines = [f"🔄 <b>Recent Token Transfers</b>"]
                lines.append(f"<b>Address:</b> <code>{address}</code>")
                lines.append("")
                for i, t in enumerate(transfers_list[:5], 1):
                    mint = t.get("mintAddress", "Unknown Token")
                    amount = t.get("amount", "?")
                    sender = t.get("senderAddress", "?")
                    receiver = t.get("receiverAddress", "?")
                    time = t.get("blockTime", "?")
                    instruction = t.get("instructionName", "Transfer")
                    try:
                        formatted_time = format_time(time) if isinstance(time, (int, float)) else time
                    except:
                        formatted_time = time
                    lines.append(f"<b>📤 Transfer #{i}</b>")
                    lines.append(f"<b>Token:</b> <code>{short_addr(mint)}</code>")
                    lines.append(f"<b>Amount:</b> {amount}")
                    lines.append(f"<b>From:</b> <code>{short_addr(sender)}</code>")
                    lines.append(f"<b>To:</b> <code>{short_addr(receiver)}</code>")
                    lines.append(f"<b>Time:</b> {formatted_time}")
                    if instruction and instruction != "Transfer":
                        lines.append(f"<b>Type:</b> {instruction}")
                    lines.append("")
                if len(transfers_list) > 5:
                    lines.append(f"<i>...and {len(transfers_list) - 5} more transfers</i>")
                await wait_msg.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=token_tools_keyboard())
            elif transfers:
                formatted_data = format_raw_data(transfers, max_chars=1000, max_items=3)
                await wait_msg.edit_text(
                    f"<b>🔄 Token Transfers (Formatted):</b>\n<pre>{formatted_data}</pre>",
                    parse_mode="HTML",
                    reply_markup=token_tools_keyboard()
                )
            else:
                await wait_msg.edit_text("😕 I couldn't find any transfers for this address. The address may not have any recorded transfers or hasn't been indexed yet.", parse_mode="HTML", reply_markup=token_tools_keyboard())
        except Exception as e:
            formatted_error = format_raw_data({"error": str(e)}, max_chars=1000)
            await wait_msg.edit_text(
                f"🙁 Error fetching token transfers:\n<pre>{formatted_error}</pre>",
                parse_mode="HTML",
                reply_markup=token_tools_keyboard()
            )
        
        user_states[user_id] = {"step": "idle", "temp": {}}
        return

    # Default handler for unrecognized text input when idle
    if state == "idle":
        await message.reply(
            "I didn't understand that. Please use the buttons or commands like /start or /cancel.",
            reply_markup=main_menu_keyboard()
        )

# --- API Helpers ---
async def fetch_wallet_holdings(wallet_address):
    url = f"https://api.vybenetwork.xyz/account/token-balance/{wallet_address}"
    headers = {"X-API-Key": VYBE_API_KEY}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data
                else:
                    # Add more logging to understand status issues
                    print(f"[LOG] Non-200 status: {resp.status} for URL: {url}")
                    text = await resp.text()
                    print(f"[LOG] Response: {text}")
    except Exception as e:
        print(f"[LOG] Exception in fetch_wallet_holdings: {e}")
    return None

async def fetch_token_symbol(token_address):
    url = f"{API_BASE}/token/{token_address}"
    headers = {"X-API-Key": VYBE_API_KEY}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("symbol")
    except Exception as e:
        print(f"[LOG] Exception in fetch_token_symbol: {e}")
    return None

async def fetch_token_price(token_address):
    # Try Vybe first
    url_vybe = f"{API_BASE}/tokens/{token_address}"
    headers_vybe = {"X-API-Key": VYBE_API_KEY}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url_vybe, headers=headers_vybe, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("price_usd") is not None:
                        return data
                else:
                    print(f"[LOG] Vybe price status: {resp.status}")
    except Exception as e:
        print(f"[LOG] Exception in fetch_token_price (Vybe): {e}")
    
    # Fallback: Birdeye
    url_birdeye = f"https://public-api.birdeye.so/public/price?address={token_address}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url_birdeye, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    price = data.get("data", {}).get("value")
                    if price is not None:
                        return {"price_usd": price, "name": token_address, "symbol": "?", "address": token_address}
    except Exception as e:
        print(f"[LOG] Exception in fetch_token_price (Birdeye): {e}")
    return None

async def fetch_token_transfers(wallet_address, limit=10):
    url = "https://api.vybenetwork.xyz/token/transfers"
    headers = {"X-API-Key": VYBE_API_KEY}
    params = {
        "walletAddress": wallet_address,
        "limit": limit
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data
                else:
                    print(f"[LOG] Token transfers status: {resp.status}")
                    text = await resp.text()
                    print(f"[LOG] Response: {text}")
    except Exception as e:
        print(f"[LOG] Exception in fetch_token_transfers: {e}")
    return None

async def fetch_vybe_markets(program_id=None):
    url = "https://api.vybenetwork.xyz/price/markets"
    # Use the exact header format from the curl example
    headers = {"X-API-KEY": VYBE_API_KEY, "accept": "application/json"}
    params = {}
    if program_id:
        params["programId"] = program_id
    
    print(f"[LOG] Fetching markets with: URL={url}, Program ID={program_id}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params, timeout=10) as resp:
                print(f"[LOG] Markets status: {resp.status}")
                if resp.status == 200:
                    data = await resp.json()
                    return data
                else:
                    text = await resp.text()
                    print(f"[LOG] Response: {text}")
    except Exception as e:
        print(f"[LOG] Exception in fetch_vybe_markets: {e}")
    return None

async def fetch_token_transfers_by_mint(mint_address, limit=5):
    url = "https://api.vybenetwork.xyz/token/transfers"
    headers = {"X-API-Key": VYBE_API_KEY}
    params = {"mintAddress": mint_address, "limit": limit}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params, timeout=10) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception as e:
        print(f"[INFO] Token transfers (mint) failed: {e}")
    return None

async def fetch_token_ohlcv(mint_address, resolution="1d", limit=7):
    url = f"https://api.vybenetwork.xyz/price/{mint_address}/token-ohlcv"
    headers = {"X-API-Key": VYBE_API_KEY}
    params = {"resolution": resolution, "limit": limit}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params, timeout=10) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception as e:
        print(f"[INFO] Token OHLCV failed: {e}")
    return None

async def fetch_token_holders(mint_address, limit=5):
    url = f"https://api.vybenetwork.xyz/token/{mint_address}/top-holders"
    headers = {"X-API-Key": VYBE_API_KEY}
    params = {"limit": limit}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params, timeout=10) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception as e:
        print(f"[INFO] Token holders failed: {e}")
    return None

async def fetch_instruction_names():
    url = "https://api.vybenetwork.xyz/token/instruction-names"
    headers = {"X-API-KEY": VYBE_API_KEY, "accept": "application/json"}
    
    print(f"[LOG] Fetching instruction names from: {url}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=10) as resp:
                print(f"[LOG] Instruction names status: {resp.status}")
                
                if resp.status == 200:
                    try:
                        data = await resp.json()
                        return data
                    except Exception as e:
                        print(f"[LOG] JSON parse error: {e}")
                        text = await resp.text()
                        return {"raw_text": text}
                else:
                    text = await resp.text()
                    print(f"[LOG] Error response: {text}")
                    return {"error": f"Status {resp.status}", "response": text}
    except Exception as e:
        print(f"[LOG] Exception in fetch_instruction_names: {e}")
        return {"error": str(e)}
    return None

async def fetch_token_transfers(address, limit=10):
    url = "https://api.vybenetwork.xyz/token/transfers"
    headers = {"X-API-KEY": VYBE_API_KEY, "accept": "application/json"}
    
    # Try to determine if this is a wallet address or mint address (basic heuristic)
    params = {"limit": limit}
    
    # For simplicity we'll pass it as walletAddress, API should handle it
    params["walletAddress"] = address
    
    print(f"[LOG] Fetching token transfers from: {url} with params: {params}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params, timeout=10) as resp:
                print(f"[LOG] Token transfers status: {resp.status}")
                
                if resp.status == 200:
                    try:
                        data = await resp.json()
                        return data
                    except Exception as e:
                        print(f"[LOG] JSON parse error: {e}")
                        text = await resp.text()
                        return {"raw_text": text}
                else:
                    text = await resp.text()
                    print(f"[LOG] Error response: {text}")
                    return {"error": f"Status {resp.status}", "response": text}
    except Exception as e:
        print(f"[LOG] Exception in fetch_token_transfers: {e}")
        return {"error": str(e)}
    return None

async def fetch_token_details(mint_address):
    url = f"https://api.vybenetwork.xyz/token/{mint_address}"
    headers = {"X-API-KEY": VYBE_API_KEY, "accept": "application/json"}
    
    print(f"[LOG] Fetching token details from: {url}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=10) as resp:
                print(f"[LOG] Token details status: {resp.status}")
                
                if resp.status == 200:
                    try:
                        data = await resp.json()
                        return data
                    except Exception as e:
                        print(f"[LOG] JSON parse error: {e}")
                        text = await resp.text()
                        return {"raw_text": text}
                else:
                    text = await resp.text()
                    print(f"[LOG] Error response: {text}")
                    return {"error": f"Status {resp.status}", "response": text}
    except Exception as e:
        print(f"[LOG] Exception in fetch_token_details: {e}")
        return {"error": str(e)}
    return None

# --- Utility Functions ---
def short_addr(addr):
    if not addr or len(addr) < 10:
        return addr or "?"
    return addr[:5] + "..." + addr[-5:]

def format_time(ts):
    try:
        dt = datetime.datetime.utcfromtimestamp(int(ts))
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(ts)

# --- New: Utility to format raw API data for Telegram display ---
def format_raw_data(data: Any, max_chars: int = 1000, max_items: int = 3) -> str:
    """
    Format raw API data for display in Telegram chat.
    Args:
        data: The raw data (dict, list, str, etc.) from the API.
        max_chars: Maximum number of characters to display.
        max_items: Maximum number of items to show if data is a list.
    Returns:
        A formatted string suitable for Telegram.
    """
    try:
        if isinstance(data, str):
            if len(data) > max_chars:
                return f"{data[:max_chars]}...(truncated)"
            return data
        if isinstance(data, list):
            if not data:
                return "Empty list"
            lines = [f"List with {len(data)} items (showing up to {max_items}):"]
            for i, item in enumerate(data[:max_items], 1):
                formatted_item = format_raw_data(item, max_chars=200, max_items=2)
                lines.append(f"{i}. {formatted_item}")
            if len(data) > max_items:
                lines.append(f"...and {len(data) - max_items} more items")
            return "\n".join(lines)
        if isinstance(data, dict):
            lines = ["Dictionary data:"]
            priority_fields = ['name', 'symbol', 'address', 'mintAddress', 'amount', 'value', 'error']
            shown_fields = 0
            for key in priority_fields:
                if key in data and shown_fields < 5:
                    value = data[key]
                    if isinstance(value, (dict, list)):
                        value = format_raw_data(value, max_chars=200, max_items=2)
                    lines.append(f" • {key.capitalize()}: {value}")
                    shown_fields += 1
            for key, value in data.items():
                if key not in priority_fields and shown_fields < 5:
                    if isinstance(value, (dict, list)):
                        value = format_raw_data(value, max_chars=200, max_items=2)
                    lines.append(f" • {key.capitalize()}: {value}")
                    shown_fields += 1
            if len(data) > shown_fields:
                lines.append(f"...and {len(data) - shown_fields} more fields")
            return "\n".join(lines)
        json_str = json.dumps(data, indent=2)
        if len(json_str) > max_chars:
            json_str = json_str[:max_chars] + "...(truncated)"
        return json_str
    except Exception as e:
        return f"Error formatting data: {str(e)}"

# --- Main Execution ---
async def main():
    print("Starting WhaleVybe polling...") # Updated name
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main()) 

@dp.callback_query(lambda c: c.data == "end_chat")
async def process_end_chat(callback_query: CallbackQuery):
    print("[DEBUG] process_end_chat handler triggered")
    user_id = callback_query.from_user.id
    user_states[user_id] = {"step": "idle", "temp": {}} # Clear state
    await callback_query.answer("Ending chat...")
    await callback_query.message.edit_text(
        "<b>👋 Thank you for vybing with WhaleVybe!</b>\n\n"
        "We hope you found what you needed and enjoyed exploring Solana with us.\n\n"
        "<i>Remember, the blockchain never sleeps—and neither do we!</i>\n\n"
        "Come back anytime to track wallets, check tokens, or just to say hi.\n\n"
        "<b>✨ Stay curious. Stay secure. Stay vybing!</b>\n\n"
        "Use /start to begin a new session.",
        parse_mode="HTML",
        reply_markup=None # Remove the keyboard
    ) 
