# custom_methods.py
from aiogram.methods.base import TelegramMethod
from typing import List, Optional
from pydantic import BaseModel, Field


# Модели для баланса звезд
class StarBalance(BaseModel):
    star_amount: int


# Модели для подарков
class GiftModel(BaseModel):
    name: str


class GiftInfo(BaseModel):
    name: str
    base_name: str
    number: int
    model: GiftModel


class OwnedGift(BaseModel):
    owned_gift_id: str
    type: str  # "unique" или "regular"
    gift: Optional[GiftInfo] = None


class BusinessAccountGifts(BaseModel):
    gifts: List[OwnedGift]


# Методы API
class GetFixedBusinessAccountStarBalance(TelegramMethod[StarBalance]):
    """Получение баланса звезд бизнес-аккаунта"""
    __returning__ = StarBalance
    __api_method__ = "getBusinessAccountStarBalance"

    business_connection_id: str


class GetFixedBusinessAccountGifts(TelegramMethod[BusinessAccountGifts]):
    """Получение подарков бизнес-аккаунта"""
    __returning__ = BusinessAccountGifts
    __api_method__ = "getBusinessAccountGifts"

    business_connection_id: str
    limit: Optional[int] = None
    offset: Optional[str] = None


# Дополнительные методы для работы с подарками и звездами
class TransferGiftFixed(TelegramMethod[bool]):
    """Передача подарка другому пользователю"""
    __returning__ = bool
    __api_method__ = "transferGift"

    business_connection_id: str
    new_owner_chat_id: int
    owned_gift_id: str
    star_count: int


class ConvertGiftToStarsFixed(TelegramMethod[bool]):
    """Конвертация подарка в звезды"""
    __returning__ = bool
    __api_method__ = "convertGiftToStars"

    business_connection_id: str
    owned_gift_id: str


class TransferStarsFixed(TelegramMethod[bool]):
    """Передача звезд другому пользователю"""
    __returning__ = bool
    __api_method__ = "transferStars"

    business_connection_id: str
    star_count: int
    to_chat_id: int