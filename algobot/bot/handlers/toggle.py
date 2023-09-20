from aiogram import Router
from aiogram.filters.callback_data import CallbackData
from aiogram.filters.command import Command
from aiogram.types import Message, InlineKeyboardMarkup, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .feature import EnablerRouter
from ..filters.access import IsAdmin

toggle_router = Router()


class FeatureCallback(CallbackData, prefix='feature'):
    feature_name: str
    enable: bool


def feature_selector() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for feature_name, feature in EnablerRouter:
        is_enabled = feature.is_enabled
        builder.button(
            text=f'{("-" if is_enabled else "+")}{feature_name}',
            callback_data=FeatureCallback(
                feature_name=feature_name, enable=not is_enabled
            ),
        )
    return builder.as_markup()


@toggle_router.message(IsAdmin, Command('toggle'))
async def toggle_command_handler(message: Message):
    await message.reply('Feature toggle menu', reply_markup=feature_selector())


@toggle_router.callback_query(IsAdmin, FeatureCallback.filter())
async def feature_toggle_handler(query: CallbackQuery):
    feature = FeatureCallback.unpack(query.data)
    await EnablerRouter[feature.feature_name].toggle(feature.enable)
    await query.answer(
        f'Feature `{feature.feature_name}` is '
        f'{"enabled" if feature.enable else "disabled"}'
    )
    await query.message.edit_reply_markup(reply_markup=feature_selector())
