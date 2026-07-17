# Buttons
btn-lang-ru = 🇷🇺 Русский
btn-lang-en = 🇬🇧 English
btn-features = 🚀 Features
btn-info = ℹ️ About Bot

# Messages
msg-welcome-new = 👋 Hello! Choose a language to continue:

msg-welcome-main = 👋 <b>Welcome to MineTracker!</b>

    A powerful and fast bot for Minecraft server monitoring. We protect you from spam, show online status right in your group, and help manage your server!

msg-lang-set = ✅ <b>Language set to English!</b>

msg-features = 🚀 <b>Features (Free tier)</b>

    🔹 Server ping every <b>300 seconds</b> (5 minutes).
    🔹 Monitoring <b>1 server</b> per group.
    🔹 Protection against fake IPs (SSRF) and spam.
    🔹 Detailed online status and MOTD.

    To start, add the bot to a group and use <code>/set_chat_server &lt;ip&gt;</code>!

msg-info = ℹ️ <b>About MineTracker Bot</b>

    Created for server owners and gaming communities. Monitor your server status in real time, keeping your chat active and bringing players together.

btn-instruction = 📖 Instruction
btn-commands = 📋 Commands List
btn-support = 🆘 Support
btn-ticket = 🎫 Create a ticket
btn-help-info = 🛠 Issue with /info
btn-help-add = 🔌 Cannot add bot to chat
btn-help-track = 📡 Cannot setup server tracking
btn-instr-info = ℹ️ How to use /info
btn-instr-add = ➕ How to add to chat
btn-instr-track = ⚙️ Setup tracking
btn-instr-track-multi = ⚙️ Setup multi-tracking
btn-back = 🔙 Back

msg-help-main = 💡 <b>Support Section</b>

    If you are having trouble using the bot, select a problem category below. You can also read instructions or create a ticket for developers.

msg-help-group = ⚠️ <b>This command is only available in private messages.</b>

    Please switch to private messages with the bot for assistance.
    <a href="https://t.me/{ $bot_username }?start=help">Go to PM</a>

msg-commands-group = ⚠️ <b>This command is only available in private messages.</b>

    Please switch to private messages with the bot to view commands.
    <a href="https://t.me/{ $bot_username }?start=commands">Go to PM</a>

msg-instr-info-text = ℹ️ <b>Using information commands</b>

    Commands <code>/info</code>, <code>/players</code>, <code>/ping</code>, <code>/motd</code>, <code>/version</code>, <code>/ip</code> work similarly: you pass the server IP after the command.
    Example: <code>/info mc.hypixel.net</code>

    <b>Limits:</b> Server queries are cached for 5 minutes for spam protection.

msg-instr-add-text = ➕ <b>How to add the bot to a chat</b>

    1. Open the bot's profile.
    2. Click "Add to Group or Channel".
    3. Select your group.
    4. Grant the bot administrator permissions so it can pin messages and manage status.

msg-instr-track-text = ⚙️ <b>How to setup server tracking</b>

    1. Ensure the bot is in your group and has admin permissions.
    2. Send the command <code>/set_chat_server &lt;IP&gt;</code> in the group.
    3. The bot will start monitoring the server and pin a status message in the group.

msg-instr-track-multi-text = ⚙️ <b>Setting up multiple servers</b>

    In the free version, you can only track <b>one</b> server per chat. To track a second server, you can add the bot to another chat or purchase Premium (in development).

msg-support-info-text = 🛠 <b>Issue with /info command</b>

    If the <code>/info</code> command shows no data:
    - Check if the IP address is correct.
    - Ensure the server is online and responds to ping (`enable-query=true` in `server.properties` for detailed info).
    - The server might be blocking queries from datacenters (Anti-DDoS).

msg-support-add-text = 🔌 <b>Cannot add bot to chat</b>

    If you can't add the bot:
    - Check your group settings (adding bots might be restricted).
    - Ensure you have admin rights in the group to invite bots.

msg-support-track-text = 📡 <b>Cannot setup tracking</b>

    If the bot is not updating the server status:
    - Check if the bot has admin permissions (especially pinning and editing messages).
    - Make sure you typed the <code>/set_chat_server</code> command correctly.

msg-commands-list = 📋 <b>Available Commands:</b>

    🔹 /start — Restart bot
    🔹 /help — Help and instructions
    🔹 /info &lt;ip&gt; — Full server status
    🔹 /players &lt;ip&gt; — Players online
    🔹 /ping &lt;ip&gt; — Check ping
    🔹 /motd &lt;ip&gt; — Get MOTD
    🔹 /version &lt;ip&gt; — Check version
    🔹 /ip &lt;ip&gt; — Safe IP address
    🔹 /configuration — Bot settings (group admins only)

msg-commands-admin-list = 
    👑 <b>Admin Commands:</b>
    🔹 /moder — Moderator panel
    🔹 /tickets — Manage tickets
msg-maintenance = 🛠 The bot is currently under maintenance. Please wait...

cmd-start-desc = Start bot
cmd-info-desc = Server status
cmd-players-desc = Players list
cmd-ping-desc = Check ping
cmd-motd-desc = Get MOTD
cmd-version-desc = Server version
cmd-ip-desc = Get IP address
cmd-help-desc = Help
cmd-commands-desc = Update commands menu
cmd-configuration-desc = Settings
cmd-set-chat-server-desc = Bind server
cmd-set-chat-gamechat-desc = Setup gamechat
cmd-auth-desc = Authentication
cmd-moder-desc = Moderator panel
cmd-tickets-desc = Manage tickets
cmd-maintenance-desc = Maintenance mode

status-on = 🔴 ENABLED
status-off = 🟢 DISABLED
status-auto-on = 🔴 ACTIVE (DB Error)
status-auto-off = 🟢 NORMAL
msg-users-cannot-use = Users can no longer use the bot.
msg-users-can-use = Users can now use the bot.
msg-maintenance-control = 🛠 <b>Maintenance Mode Control</b>
msg-manual-mode = Manual mode
msg-auto-mode = Auto mode (DB crash)
msg-error-send-user = ❌ Error sending to user:
    <code>{ $error }</code>

msg-admin-alert-db-error = 🚨 <b>ALERT! Bot entered automatic maintenance mode!</b>
msg-admin-alert-db-error-count = Database error occurred (failure count: { $count })
msg-admin-alert-db-ok = ✅ <b>Database is available again!</b>
    Bot returns to normal operation mode.

status-offline = Status: Offline
msg-last-update-recently = Last updated recently.
status-online = Status: Online
msg-ping = Ping
msg-players = Players
msg-displayed = Displayed
msg-calculating = Calculating
msg-updated-automatically = Updated automatically
msg-commands-updated = ✅ <b>Commands menu successfully updated!</b>

msg-internal-error = Oops! Something went wrong on our side. The developers have been notified.
msg-group-welcome = 👋 Hello everyone! I am MineTracker.
    To set up server monitoring in this chat, an administrator should use the command <code>/set_chat_server &lt;ip&gt;</code>
