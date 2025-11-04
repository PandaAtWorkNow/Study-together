from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import default_state
from aiogram.types import Message, WebAppInfo
from logging import getLogger
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

router = Router()
log = getLogger(__name__)


@router.message(CommandStart)
async def command_start(message: Message):
    log.info('start menu default')
    await message.answer(text='efdfsd', reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='кликай', url='https://m.vk.com/video7266823_78234740')],
        [InlineKeyboardButton(text='жми', url='https://yandex.ru/video/touch/preview/8250732885115643543?text=%D1%80%D0%B5%D0%BA%D1%80%D0%BE%D0%BB%20%D1%81%D1%81%D1%8B%D0%BB%D0%BA%D0%B0%20%D0%BD%D0%B0%20%D0%B2%D0%B8%D0%B4%D0%B5%D0%BE&path=yandex_search&parent-reqid=1762275952021069-9211158593450198942-balancer-l7leveler-kubr-yp-vla-265-BAL&from_type=vast')],
        [InlineKeyboardButton(text='тыкни', web_app=WebAppInfo(url='https://yandex.ru/video/preview/17193376190839247531?text=порно%20с%20конями&path=yandex_search&parent-reqid=1762276638743991-3842274031912798246-balancer-l7leveler-kubr-yp-vla-101-BAL&from_type=carousel'))],
        [InlineKeyboardButton(text='сиськи', web_app=WebAppInfo(url='https://pandaatworknow.github.io/Study-together/'))]
    ]))