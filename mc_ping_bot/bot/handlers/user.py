from aiogram import Router, F
router = Router()
router.message.filter(F.chat.type == "private")
