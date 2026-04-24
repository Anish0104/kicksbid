from datetime import datetime
from typing import Optional

from flask_login import UserMixin
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from extensions import db


LOCAL_CUTOUT_IMAGE_BY_STYLE_CODE = {
    "FN7649-110": "/static/images/cutouts/FN7649-110.png",
    "FV2345-100": "/static/images/cutouts/FV2345-100.png",
    "CP9654": "/static/images/cutouts/CP9654.png",
}


IMAGE_URL_BY_STYLE_CODE = {
    "555088-023": "https://images.stockx.com/images/Air-Jordan-1-Retro-High-OG-Bred-Patent-Product.jpg",
    "CP9654": "https://images.stockx.com/images/adidas-Yeezy-Boost-350-V2-Zebra-Product.jpg",
    "CW2288-111": "https://images.stockx.com/images/Nike-Air-Force-1-07-White-Product.jpg",
    "U990TC6": "https://images.stockx.com/images/New-Balance-990v6-Grey-Product.jpg",
    "FV2345-100": "https://images.stockx.com/images/Nike-LeBron-21-Akoya-Product.jpg",
    "DZ4137-106": "https://images.stockx.com/images/Air-Jordan-1-Retro-High-OG-Bred-Patent-Product.jpg",
    "1201A019-108": "https://images.stockx.com/images/ASICS-Gel-Kayano-14-Cream-Black-Metallic-Plum-Product.jpg",
    "FN7649-110": "https://images.stockx.com/images/Nike-Air-Force-1-Low-Stussy-Black-Product.jpg",
    "U9060HSC": "https://images.stockx.com/images/New-Balance-990v6-Grey-Product.jpg",
    "IF1864": "https://images.stockx.com/images/adidas-AE-1-New-Wave-Product.jpg",
    "FV4921-600": "https://images.stockx.com/images/Nike-Kobe-6-Protro-Reverse-Grinch-Product.jpg",
    "FV5029-141": "https://images.stockx.com/images/Air-Jordan-4-Retro-Military-Blue-2024-Product.jpg",
    "DN3707-100": "https://images.stockx.com/images/Air-Jordan-3-Retro-White-Cement-Reimagined-Product.jpg",
    "DR5415-103": "https://images.stockx.com/images/Air-Jordan-4-Retro-SB-Pine-Green-Product.jpg",
    "M990SB2": "https://images.stockx.com/images/New-Balance-990v2-Salehe-Bembury-Sand-Be-The-Time-Product.jpg",
    "ML2002RJ": "https://images.stockx.com/images/New-Balance-990v6-Grey-Product.jpg",
}


FALLBACK_IMAGE_BY_BRAND = {
    "jordan": "https://images.stockx.com/images/Air-Jordan-4-Retro-Military-Blue-2024-Product.jpg",
    "nike": "https://images.stockx.com/images/Nike-Air-Force-1-07-White-Product.jpg",
    "adidas": "https://images.stockx.com/images/adidas-Yeezy-Boost-350-V2-Zebra-Product.jpg",
    "new balance": "https://images.stockx.com/images/New-Balance-990v6-Grey-Product.jpg",
    "asics": "https://images.stockx.com/images/ASICS-Gel-Kayano-14-Cream-Black-Metallic-Plum-Product.jpg",
}


def build_item_image_url(
    style_code: str,
    brand: str,
    model_name: str,
    image_url_override: Optional[str] = None,
) -> str:
    if image_url_override:
        return image_url_override

    if style_code in LOCAL_CUTOUT_IMAGE_BY_STYLE_CODE:
        return LOCAL_CUTOUT_IMAGE_BY_STYLE_CODE[style_code]

    if style_code in IMAGE_URL_BY_STYLE_CODE:
        return IMAGE_URL_BY_STYLE_CODE[style_code]

    brand_key = (brand or "").strip().lower()
    if brand_key in FALLBACK_IMAGE_BY_BRAND:
        return FALLBACK_IMAGE_BY_BRAND[brand_key]

    return "https://images.stockx.com/images/Nike-Air-Force-1-07-White-Product.jpg"


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    items: Mapped[list["Item"]] = relationship("Item", back_populates="seller")
    bids: Mapped[list["Bid"]] = relationship("Bid", back_populates="bidder")
    autobids: Mapped[list["AutoBid"]] = relationship("AutoBid", back_populates="bidder")
    notifications: Mapped[list["Notification"]] = relationship("Notification", back_populates="user")
    alerts: Mapped[list["Alert"]] = relationship("Alert", back_populates="user")
    questions: Mapped[list["Question"]] = relationship("Question", back_populates="user")
    answers: Mapped[list["Answer"]] = relationship("Answer", back_populates="rep")


class Category(db.Model):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories.id"), nullable=True)

    subcategories: Mapped[list["Category"]] = relationship(
        "Category",
        back_populates="parent",
        foreign_keys="Category.parent_id",
    )
    parent: Mapped[Optional["Category"]] = relationship(
        "Category",
        back_populates="subcategories",
        remote_side="Category.id",
        foreign_keys="Category.parent_id",
    )
    items: Mapped[list["Item"]] = relationship("Item", back_populates="category")
    alerts: Mapped[list["Alert"]] = relationship("Alert", back_populates="category")


class Item(db.Model):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    brand: Mapped[str] = mapped_column(String(100), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    colorway: Mapped[str] = mapped_column(String(100), nullable=False)
    style_code: Mapped[str] = mapped_column(String(50), nullable=False)
    us_size: Mapped[float] = mapped_column(Float, nullable=False)
    condition: Mapped[str] = mapped_column(String(10), nullable=False)
    box_included: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    start_price: Mapped[float] = mapped_column(Float, nullable=False)
    reserve_price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    bid_increment: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    image_url_override: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    close_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    seller: Mapped["User"] = relationship("User", back_populates="items")
    category: Mapped["Category"] = relationship("Category", back_populates="items")
    bids: Mapped[list["Bid"]] = relationship("Bid", back_populates="item", cascade="all, delete-orphan")
    autobids: Mapped[list["AutoBid"]] = relationship("AutoBid", back_populates="item", cascade="all, delete-orphan")
    questions: Mapped[list["Question"]] = relationship("Question", back_populates="item", cascade="all, delete-orphan")

    @property
    def image_url(self) -> str:
        return build_item_image_url(
            self.style_code,
            self.brand,
            self.model_name,
            self.image_url_override,
        )


class Bid(db.Model):
    __tablename__ = "bids"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    bidder_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    placed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    is_auto: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    item: Mapped["Item"] = relationship("Item", back_populates="bids")
    bidder: Mapped["User"] = relationship("User", back_populates="bids")


class AutoBid(db.Model):
    __tablename__ = "autobids"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    bidder_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    upper_limit: Mapped[float] = mapped_column(Float, nullable=False)

    item: Mapped["Item"] = relationship("Item", back_populates="autobids")
    bidder: Mapped["User"] = relationship("User", back_populates="autobids")


class Alert(db.Model):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    keywords: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="alerts")
    category: Mapped["Category"] = relationship("Category", back_populates="alerts")


class Question(db.Model):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="questions")
    item: Mapped["Item"] = relationship("Item", back_populates="questions")
    answers: Mapped[list["Answer"]] = relationship("Answer", back_populates="question", cascade="all, delete-orphan")


class Answer(db.Model):
    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), nullable=False)
    rep_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    question: Mapped["Question"] = relationship("Question", back_populates="answers")
    rep: Mapped["User"] = relationship("User", back_populates="answers")


class Notification(db.Model):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="notifications")
