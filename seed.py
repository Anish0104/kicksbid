from datetime import datetime, timedelta

from app import app
from extensions import db
from models import Answer, Alert, AutoBid, Bid, Category, Item, Notification, Question, User
from werkzeug.security import generate_password_hash


with app.app_context():
    db.session.execute(db.text("SET FOREIGN_KEY_CHECKS = 0"))
    db.session.query(Answer).delete(synchronize_session=False)
    db.session.query(Question).delete(synchronize_session=False)
    db.session.query(Alert).delete(synchronize_session=False)
    db.session.query(Notification).delete(synchronize_session=False)
    db.session.query(AutoBid).delete(synchronize_session=False)
    db.session.query(Bid).delete(synchronize_session=False)
    db.session.query(Item).delete(synchronize_session=False)
    db.session.query(User).delete(synchronize_session=False)
    db.session.query(Category).delete(synchronize_session=False)
    db.session.execute(db.text("SET FOREIGN_KEY_CHECKS = 1"))
    db.session.commit()

    root = Category(name="Sneakers")
    db.session.add(root)
    db.session.flush()

    running = Category(name="Running", parent_id=root.id)
    basketball = Category(name="Basketball", parent_id=root.id)
    lifestyle = Category(name="Lifestyle / Casual", parent_id=root.id)
    deadstock = Category(name="Deadstock & Collectors", parent_id=root.id)
    db.session.add_all([running, basketball, lifestyle, deadstock])
    db.session.flush()

    alice = User(username="alice", email="alice@test.com", password_hash=generate_password_hash("password"), role="user")
    bob = User(username="bob_kicks", email="bob@test.com", password_hash=generate_password_hash("password"), role="user")
    sarah = User(username="rep_sarah", email="sarah@kicksbid.com", password_hash=generate_password_hash("rep"), role="rep")
    admin = User(username="admin", email="admin@kicksbid.com", password_hash=generate_password_hash("admin123"), role="admin")
    db.session.add_all([alice, bob, sarah, admin])
    db.session.flush()

    now = datetime.utcnow()
    items = [
        Item(
            title="Air Jordan 1 Retro High OG Bred",
            brand="Nike",
            model_name="Air Jordan 1",
            colorway="Black/Red",
            style_code="555088-001",
            us_size=10.0,
            condition="DS",
            box_included=True,
            description="Iconic Bred colorway. Brand new deadstock.",
            seller_id=bob.id,
            category_id=deadstock.id,
            start_price=800,
            reserve_price=1100,
            bid_increment=25,
            close_time=now + timedelta(days=2),
        ),
        Item(
            title="Adidas Yeezy Boost 350 V2 Zebra",
            brand="Adidas",
            model_name="Yeezy Boost 350 V2",
            colorway="White/Black",
            style_code="CP9654",
            us_size=9.5,
            condition="VNDS",
            box_included=True,
            description="Worn once, near deadstock condition.",
            seller_id=bob.id,
            category_id=deadstock.id,
            start_price=500,
            reserve_price=750,
            bid_increment=10,
            close_time=now + timedelta(hours=6),
        ),
        Item(
            title="Nike Air Force 1 Low White",
            brand="Nike",
            model_name="Air Force 1",
            colorway="White/White",
            style_code="CW2288-111",
            us_size=11.0,
            condition="Used",
            box_included=False,
            description="Classic all white. Some wear on soles.",
            seller_id=bob.id,
            category_id=lifestyle.id,
            start_price=60,
            reserve_price=90,
            bid_increment=5,
            close_time=now + timedelta(days=4),
        ),
        Item(
            title="New Balance 990v5 Grey",
            brand="New Balance",
            model_name="990v5",
            colorway="Grey",
            style_code="M990GL5",
            us_size=10.5,
            condition="DS",
            box_included=True,
            description="Made in USA. Brand new in box.",
            seller_id=bob.id,
            category_id=running.id,
            start_price=180,
            reserve_price=220,
            bid_increment=10,
            close_time=now + timedelta(days=3),
        ),
        Item(
            title="Nike LeBron 21 Akoya",
            brand="Nike",
            model_name="LeBron 21",
            colorway="Blue/Gold",
            style_code="FB2238-001",
            us_size=12.0,
            condition="DS",
            box_included=True,
            description="Latest LeBron signature. Brand new.",
            seller_id=bob.id,
            category_id=basketball.id,
            start_price=150,
            reserve_price=200,
            bid_increment=10,
            close_time=now + timedelta(days=5),
        ),
        Item(
            title="Travis Scott x Air Jordan 1 Low OG",
            brand="Nike",
            model_name="Air Jordan 1 Low",
            colorway="Sail/Mocha",
            style_code="CQ4277-001",
            us_size=9.0,
            condition="DS",
            box_included=True,
            description="Travis Scott collab. Extremely rare.",
            seller_id=bob.id,
            category_id=deadstock.id,
            start_price=400,
            reserve_price=600,
            bid_increment=15,
            close_time=now + timedelta(days=1),
        ),
    ]
    db.session.add_all(items)
    db.session.flush()

    bids = [
        Bid(item_id=items[0].id, bidder_id=alice.id, amount=850, placed_at=now - timedelta(hours=3), is_auto=False),
        Bid(item_id=items[0].id, bidder_id=alice.id, amount=900, placed_at=now - timedelta(hours=1), is_auto=False),
        Bid(item_id=items[1].id, bidder_id=alice.id, amount=520, placed_at=now - timedelta(hours=2), is_auto=False),
        Bid(item_id=items[5].id, bidder_id=alice.id, amount=425, placed_at=now - timedelta(minutes=30), is_auto=False),
    ]
    db.session.add_all(bids)
    db.session.commit()

    print("KicksBid seeded successfully!")
