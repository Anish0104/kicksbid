from datetime import datetime
from typing import Optional

from flask_login import UserMixin
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from extensions import db


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
    close_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    seller: Mapped["User"] = relationship("User", back_populates="items")
    category: Mapped["Category"] = relationship("Category", back_populates="items")
    bids: Mapped[list["Bid"]] = relationship("Bid", back_populates="item", cascade="all, delete-orphan")
    autobids: Mapped[list["AutoBid"]] = relationship("AutoBid", back_populates="item", cascade="all, delete-orphan")
    questions: Mapped[list["Question"]] = relationship("Question", back_populates="item", cascade="all, delete-orphan")


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
