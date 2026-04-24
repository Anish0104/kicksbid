import sys
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, or_, select
from werkzeug.security import generate_password_hash

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import app
from extensions import db
from models import Answer, Alert, AutoBid, Bid, Category, Item, Notification, Question, User
from seed import bootstrap_categories


DEMO_USERS = {
    "demo_seller_one": {
        "email": "demo.seller.one@kicksbid.local",
        "password": "password",
        "role": "user",
    },
    "demo_seller_two": {
        "email": "demo.seller.two@kicksbid.local",
        "password": "password",
        "role": "user",
    },
    "demo_bidder_mia": {
        "email": "demo.bidder.mia@kicksbid.local",
        "password": "password",
        "role": "user",
    },
    "demo_bidder_luca": {
        "email": "demo.bidder.luca@kicksbid.local",
        "password": "password",
        "role": "user",
    },
    "demo_bidder_zoe": {
        "email": "demo.bidder.zoe@kicksbid.local",
        "password": "password",
        "role": "user",
    },
    "demo_rep": {
        "email": "demo.rep@kicksbid.local",
        "password": "password",
        "role": "rep",
    },
}


DEMO_ITEMS = [
    {
        "key": "bred_jordan",
        "title": "Air Jordan 1 Retro High OG Bred",
        "brand": "Jordan",
        "model_name": "Air Jordan 1",
        "colorway": "Black / Varsity Red / White",
        "style_code": "555088-023",
        "us_size": 10.0,
        "condition": "New",
        "box_included": True,
        "description": "Fresh pair with sharp leather panels, clean wings logo, and untouched outsole.",
        "seller": "demo_seller_one",
        "category": "Retro",
        "start_price": 480,
        "reserve_price": 620,
        "bid_increment": 15,
        "close_time": lambda now: now + timedelta(days=3, hours=4),
        "status": "open",
    },
    {
        "key": "yeezy_zebra",
        "title": "adidas Yeezy Boost 350 V2 Zebra",
        "brand": "Adidas",
        "model_name": "Yeezy Boost 350 V2",
        "colorway": "White / Core Black / Red",
        "style_code": "CP9654",
        "us_size": 9.5,
        "condition": "Like New",
        "box_included": True,
        "description": "Primeknit upper is bright and the boost feels fresh with only light outsole wear.",
        "seller": "demo_seller_two",
        "category": "Collab / Limited",
        "start_price": 340,
        "reserve_price": 420,
        "bid_increment": 10,
        "close_time": lambda now: now + timedelta(days=2, hours=7),
        "status": "open",
    },
    {
        "key": "vomero_supersonic",
        "title": "Nike Zoom Vomero 5 Supersonic",
        "brand": "Nike",
        "model_name": "Zoom Vomero 5",
        "colorway": "White / Black / Neutral Grey",
        "style_code": "FN7649-110",
        "us_size": 11.5,
        "condition": "New",
        "box_included": True,
        "description": "Popular tech-runner shape with clean cage panels and plush underfoot feel.",
        "seller": "demo_seller_one",
        "category": "Running",
        "start_price": 155,
        "reserve_price": 205,
        "bid_increment": 10,
        "close_time": lambda now: now + timedelta(days=1, hours=12),
        "status": "open",
    },
    {
        "key": "new_balance_9060",
        "title": "New Balance 9060 Sea Salt Rain Cloud",
        "brand": "New Balance",
        "model_name": "9060",
        "colorway": "Sea Salt / Rain Cloud",
        "style_code": "U9060HSC",
        "us_size": 8.5,
        "condition": "Like New",
        "box_included": True,
        "description": "Minimal wear on the outsole with crisp suede and an easy everyday color mix.",
        "seller": "demo_seller_two",
        "category": "Lifestyle",
        "start_price": 140,
        "reserve_price": 185,
        "bid_increment": 5,
        "close_time": lambda now: now + timedelta(days=4, hours=1),
        "status": "open",
    },
    {
        "key": "lebron_akoya",
        "title": "Nike LeBron 21 Akoya",
        "brand": "Nike",
        "model_name": "LeBron 21",
        "colorway": "Akoya / Light Bone / Blue",
        "style_code": "FV2345-100",
        "us_size": 12.0,
        "condition": "New",
        "box_included": True,
        "description": "Performance pair with clean upper, sharp detailing, and no visible wear.",
        "seller": "demo_seller_one",
        "category": "Basketball",
        "start_price": 165,
        "reserve_price": 215,
        "bid_increment": 10,
        "close_time": lambda now: now + timedelta(days=2, hours=3),
        "status": "open",
    },
    {
        "key": "travis_olive",
        "title": "Travis Scott x Air Jordan 1 Low OG Olive",
        "brand": "Jordan",
        "model_name": "Air Jordan 1 Low OG",
        "colorway": "Sail / Black / Medium Olive",
        "style_code": "DZ4137-106",
        "us_size": 9.0,
        "condition": "New",
        "box_included": True,
        "description": "Comes with the full collab package and clean suede with sharp reverse swooshes.",
        "seller": "demo_seller_two",
        "category": "Collab / Limited",
        "start_price": 620,
        "reserve_price": 790,
        "bid_increment": 20,
        "close_time": lambda now: now + timedelta(days=5, hours=6),
        "status": "open",
    },
    {
        "key": "aj4_military_blue_archive",
        "title": "Air Jordan 4 Retro Military Blue",
        "brand": "Jordan",
        "model_name": "Air Jordan 4",
        "colorway": "Summit White / Military Blue",
        "style_code": "FV5029-141",
        "us_size": 10.5,
        "condition": "New",
        "box_included": True,
        "description": "Archive sale pair used for recent-history views and similar auction suggestions.",
        "seller": "demo_seller_one",
        "category": "Retro",
        "start_price": 290,
        "reserve_price": 340,
        "bid_increment": 10,
        "close_time": lambda now: now - timedelta(days=8),
        "status": "closed",
    },
    {
        "key": "kayano_archive",
        "title": "ASICS Gel-Kayano 14 Cream Black",
        "brand": "ASICS",
        "model_name": "Gel-Kayano 14",
        "colorway": "Cream / Black",
        "style_code": "1201A019-108",
        "us_size": 9.5,
        "condition": "Like New",
        "box_included": True,
        "description": "Older closed listing kept around so the similar-item module has real history to show.",
        "seller": "demo_seller_two",
        "category": "Running",
        "start_price": 170,
        "reserve_price": 220,
        "bid_increment": 10,
        "close_time": lambda now: now - timedelta(days=13),
        "status": "closed",
    },
]


DEMO_BIDS = [
    ("bred_jordan", "demo_bidder_mia", 520, 18),
    ("bred_jordan", "demo_bidder_luca", 550, 13),
    ("yeezy_zebra", "demo_bidder_zoe", 360, 15),
    ("yeezy_zebra", "demo_bidder_luca", 380, 9),
    ("vomero_supersonic", "demo_bidder_mia", 170, 7),
    ("new_balance_9060", "demo_bidder_zoe", 155, 11),
    ("lebron_akoya", "demo_bidder_luca", 185, 10),
    ("travis_olive", "demo_bidder_mia", 680, 14),
    ("travis_olive", "demo_bidder_zoe", 720, 6),
    ("aj4_military_blue_archive", "demo_bidder_luca", 320, 190),
    ("aj4_military_blue_archive", "demo_bidder_zoe", 335, 182),
    ("kayano_archive", "demo_bidder_mia", 180, 300),
    ("kayano_archive", "demo_bidder_luca", 200, 292),
]


DEMO_QUESTIONS = [
    {
        "item_key": "bred_jordan",
        "asker": "demo_bidder_zoe",
        "body": "Any heel drag or star loss on the outsole?",
        "answers": [
            ("demo_rep", "No heel drag. The outsole stars are still crisp and the pair has not been worn outside."),
        ],
    },
    {
        "item_key": "travis_olive",
        "asker": "demo_bidder_luca",
        "body": "Does this include all extra laces and the original box sleeve?",
        "answers": [
            ("demo_rep", "Yes. The listing includes the box, sleeve, and the extra lace set shown by the seller."),
        ],
    },
]


def fetch_ids(statement):
    return list(db.session.execute(statement).scalars())


def purge_existing_demo_data():
    demo_emails = {spec["email"] for spec in DEMO_USERS.values()}
    user_ids = fetch_ids(select(User.id).where(User.email.in_(demo_emails)))
    if not user_ids:
        return

    item_ids = fetch_ids(select(Item.id).where(Item.seller_id.in_(user_ids)))
    question_ids = fetch_ids(
        select(Question.id).where(
            or_(Question.user_id.in_(user_ids), Question.item_id.in_(item_ids or [-1]))
        )
    )

    db.session.execute(
        delete(Answer).where(or_(Answer.rep_id.in_(user_ids), Answer.question_id.in_(question_ids or [-1])))
    )
    db.session.execute(delete(Notification).where(Notification.user_id.in_(user_ids)))
    db.session.execute(delete(Alert).where(Alert.user_id.in_(user_ids)))
    db.session.execute(
        delete(AutoBid).where(or_(AutoBid.bidder_id.in_(user_ids), AutoBid.item_id.in_(item_ids or [-1])))
    )
    db.session.execute(delete(Bid).where(or_(Bid.bidder_id.in_(user_ids), Bid.item_id.in_(item_ids or [-1]))))
    db.session.execute(delete(Question).where(Question.id.in_(question_ids or [-1])))
    db.session.execute(delete(Item).where(Item.id.in_(item_ids or [-1])))
    db.session.execute(delete(User).where(User.id.in_(user_ids)))
    db.session.commit()


def main():
    with app.app_context():
        bootstrap_categories()
        db.session.commit()
        purge_existing_demo_data()

        root = Category.query.filter_by(name="Sneakers", parent_id=None).first()
        categories = {category.name: category for category in Category.query.filter_by(parent_id=root.id).all()}

        users = {}
        for username, spec in DEMO_USERS.items():
            user = User(
                username=username,
                email=spec["email"],
                password_hash=generate_password_hash(spec["password"]),
                role=spec["role"],
            )
            db.session.add(user)
            users[username] = user

        db.session.flush()

        now = datetime.utcnow()
        items = {}
        for spec in DEMO_ITEMS:
            item = Item(
                title=spec["title"],
                brand=spec["brand"],
                model_name=spec["model_name"],
                colorway=spec["colorway"],
                style_code=spec["style_code"],
                us_size=spec["us_size"],
                condition=spec["condition"],
                box_included=spec["box_included"],
                description=spec["description"],
                seller_id=users[spec["seller"]].id,
                category_id=categories[spec["category"]].id,
                start_price=spec["start_price"],
                reserve_price=spec["reserve_price"],
                bid_increment=spec["bid_increment"],
                close_time=spec["close_time"](now),
                status=spec["status"],
            )
            db.session.add(item)
            db.session.flush()
            items[spec["key"]] = item

        for item_key, bidder_key, amount, hours_ago in DEMO_BIDS:
            db.session.add(
                Bid(
                    item_id=items[item_key].id,
                    bidder_id=users[bidder_key].id,
                    amount=amount,
                    placed_at=now - timedelta(hours=hours_ago),
                    is_auto=False,
                )
            )

        db.session.flush()

        for question_spec in DEMO_QUESTIONS:
            question = Question(
                user_id=users[question_spec["asker"]].id,
                item_id=items[question_spec["item_key"]].id,
                body=question_spec["body"],
                created_at=now - timedelta(hours=4),
            )
            db.session.add(question)
            db.session.flush()

            for rep_key, body in question_spec["answers"]:
                db.session.add(
                    Answer(
                        question_id=question.id,
                        rep_id=users[rep_key].id,
                        body=body,
                        created_at=now - timedelta(hours=2),
                    )
                )

        db.session.commit()

        open_items = Item.query.filter(Item.status == "open", Item.close_time > now).count()
        total_bids = Bid.query.count()
        print(f"Loaded demo marketplace data: {open_items} live sneakers, {total_bids} bids, {len(DEMO_USERS)} demo accounts.")


if __name__ == "__main__":
    main()
