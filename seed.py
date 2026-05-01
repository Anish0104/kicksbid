import argparse
import os
from datetime import timedelta

from sqlalchemy import text
from werkzeug.security import generate_password_hash

from app import app
from db_artifacts import install_database_artifacts

from extensions import db
from models import Alert, Answer, AutoBid, Bid, Category, Item, Notification, Question, User
from time_utils import current_time


CATEGORY_TREE = {
    "Sneakers": {
        "Performance": {
            "Basketball": ["Signature", "Team"],
            "Running": ["Daily Trainer", "Race Day"],
            "Training": ["Court", "Cross-Training"],
        },
        "Lifestyle": {
            "Retro": ["High Top", "Low Top"],
            "Skate": ["Dunk-Inspired", "Cupsole"],
            "Casual": ["Slip-On", "Court Classic"],
        },
        "Collector": {
            "Collaboration": ["Designer", "Artist"],
            "Limited": ["Regional Exclusive", "Friends And Family"],
            "Vintage": ["OG Release", "Archive"],
        },
    }
}

LEGACY_CATEGORY_TARGETS = {
    ("Sneakers", "Running"): ("Sneakers", "Performance", "Running", "Daily Trainer"),
    ("Sneakers", "Basketball"): ("Sneakers", "Performance", "Basketball", "Signature"),
    ("Sneakers", "Lifestyle"): ("Sneakers", "Lifestyle", "Casual", "Court Classic"),
    ("Sneakers", "Retro"): ("Sneakers", "Lifestyle", "Retro", "High Top"),
    ("Sneakers", "Collab / Limited"): ("Sneakers", "Collector", "Collaboration", "Designer"),
}

LEGACY_CONDITION_TARGETS = {
    "New": "new",
    "new": "new",
    "Used": "used",
    "used": "used",
    "Like New": "like_new",
    "like_new": "like_new",
    "Good": "good",
    "good": "good",
    "Fair": "fair",
    "fair": "fair",
}


def ensure_category(name, parent=None):
    parent_id = parent.id if parent else None
    category = Category.query.filter_by(name=name, parent_id=parent_id).first()
    created = False
    if category is None:
        category = Category(name=name, parent_id=parent_id)
        db.session.add(category)
        db.session.flush()
        created = True
    return category, created


def category_path(category):
    lineage = []
    node = category
    while node is not None:
        lineage.append(node.name)
        node = node.parent
    return " > ".join(reversed(lineage))


def bootstrap_category_branch(name, children, parent=None, created=None):
    category, was_created = ensure_category(name, parent=parent)
    if was_created and created is not None:
        created.append(category_path(category))

    if isinstance(children, dict):
        for child_name, grand_children in children.items():
            bootstrap_category_branch(child_name, grand_children, parent=category, created=created)
    else:
        for child_name in children:
            bootstrap_category_branch(child_name, [], parent=category, created=created)


def bootstrap_categories():
    created = []
    for root_name, children in CATEGORY_TREE.items():
        bootstrap_category_branch(root_name, children, created=created)
    return created


def get_category_by_path(path):
    parent = None
    current = None
    for name in path:
        parent_id = parent.id if parent else None
        current = Category.query.filter_by(name=name, parent_id=parent_id).first()
        if current is None:
            return None
        parent = current
    return current


def migrate_legacy_categories():
    migrated = []

    for legacy_path, target_path in LEGACY_CATEGORY_TARGETS.items():
        legacy_category = get_category_by_path(legacy_path)
        target_category = get_category_by_path(target_path)

        if legacy_category is None or target_category is None:
            continue
        if legacy_category.id == target_category.id or legacy_category.subcategories:
            continue

        items_moved = Item.query.filter_by(category_id=legacy_category.id).update({"category_id": target_category.id})
        alerts_moved = Alert.query.filter_by(category_id=legacy_category.id).update({"category_id": target_category.id})

        if items_moved or alerts_moved:
            migrated.append(
                f"{legacy_category.full_name} -> {target_category.full_name} "
                f"(items: {items_moved}, alerts: {alerts_moved})"
            )

        remaining_items = Item.query.filter_by(category_id=legacy_category.id).count()
        remaining_alerts = Alert.query.filter_by(category_id=legacy_category.id).count()
        if remaining_items == 0 and remaining_alerts == 0:
            db.session.delete(legacy_category)

    return migrated


def migrate_legacy_conditions():
    migrated = []
    for legacy_value, target_value in LEGACY_CONDITION_TARGETS.items():
        if legacy_value == target_value:
            continue

        updated = Item.query.filter_by(condition=legacy_value).update({"condition": target_value})
        if updated:
            migrated.append(f"{legacy_value} -> {target_value} ({updated} items)")

    return migrated


def bootstrap_admin(username, email, password):
    admin = User.query.filter((User.username == username) | (User.email == email)).first()
    created = False

    if admin is None:
        admin = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            role="admin",
        )
        db.session.add(admin)
        created = True
    else:
        admin.username = username
        admin.email = email
        admin.password_hash = generate_password_hash(password)
        admin.role = "admin"
        admin.is_active = True

    return created, admin


def load_sql_sample_data():
    sample_users = [
        {
            "username": "jordan_fan",
            "email": "jordan@example.com",
            "password": "password",
            "role": "user",
            "created_at": current_time() - timedelta(days=30),
        },
        {
            "username": "sneakerhead_nj",
            "email": "sneaker@example.com",
            "password": "password",
            "role": "user",
            "created_at": current_time() - timedelta(days=25),
        },
        {
            "username": "kicks_collector",
            "email": "collector@example.com",
            "password": "password",
            "role": "user",
            "created_at": current_time() - timedelta(days=20),
        },
        {
            "username": "sole_seller",
            "email": "seller@example.com",
            "password": "password",
            "role": "user",
            "created_at": current_time() - timedelta(days=15),
        },
        {
            "username": "rep_mike",
            "email": "rep@kicksbid.local",
            "password": "password",
            "role": "rep",
            "created_at": current_time() - timedelta(days=60),
        },
    ]

    sample_items = [
        {
            "title": "Air Jordan 1 Retro High OG Chicago",
            "brand": "Nike",
            "model_name": "Air Jordan 1 Retro High OG",
            "colorway": "White/Black-Varsity Red",
            "style_code": "555088-101",
            "us_size": 10.5,
            "condition": "new",
            "box_included": True,
            "description": "Deadstock AJ1 Chicago colorway. Never worn, tried on once indoors. All tags attached. OG box included.",
            "seller": "sole_seller",
            "category_path": ("Sneakers", "Lifestyle", "Retro", "High Top"),
            "start_price": 350.0,
            "reserve_price": 400.0,
            "bid_increment": 10.0,
            "close_time": current_time() + timedelta(days=5),
            "status": "open",
            "created_at": current_time() - timedelta(days=2),
        },
        {
            "title": "Nike Dunk Low Panda",
            "brand": "Nike",
            "model_name": "Dunk Low",
            "colorway": "White/Black",
            "style_code": "DD1391-100",
            "us_size": 9.0,
            "condition": "like_new",
            "box_included": True,
            "description": "Worn twice. No creasing. Box included. Classic Panda colorway that goes with everything.",
            "seller": "jordan_fan",
            "category_path": ("Sneakers", "Lifestyle", "Skate", "Dunk-Inspired"),
            "start_price": 120.0,
            "reserve_price": 140.0,
            "bid_increment": 5.0,
            "close_time": current_time() + timedelta(days=3),
            "status": "open",
            "created_at": current_time() - timedelta(days=1),
        },
        {
            "title": "Adidas Yeezy Boost 350 V2 Zebra",
            "brand": "Adidas",
            "model_name": "Yeezy Boost 350 V2",
            "colorway": "White/Core Black/Red",
            "style_code": "CP9654",
            "us_size": 11.0,
            "condition": "new",
            "box_included": True,
            "description": "Brand new Zebra Yeezy. Purchased from Adidas confirmed app. 100% authentic with receipt.",
            "seller": "sneakerhead_nj",
            "category_path": ("Sneakers", "Collector", "Limited", "Regional Exclusive"),
            "start_price": 280.0,
            "reserve_price": 320.0,
            "bid_increment": 10.0,
            "close_time": current_time() + timedelta(days=7),
            "status": "open",
            "created_at": current_time() - timedelta(days=3),
        },
        {
            "title": "Nike Air Max 90 Infrared",
            "brand": "Nike",
            "model_name": "Air Max 90",
            "colorway": "White/Black-Infrared",
            "style_code": "CT1685-100",
            "us_size": 10.0,
            "condition": "good",
            "box_included": False,
            "description": "OG AM90 Infrared. Light wear on outsole. Box not included. Cleaned and ready to ship.",
            "seller": "kicks_collector",
            "category_path": ("Sneakers", "Lifestyle", "Casual", "Court Classic"),
            "start_price": 85.0,
            "reserve_price": 100.0,
            "bid_increment": 5.0,
            "close_time": current_time() + timedelta(days=4),
            "status": "open",
            "created_at": current_time() - timedelta(days=4),
        },
        {
            "title": "Jordan 4 Retro Military Black",
            "brand": "Nike",
            "model_name": "Air Jordan 4 Retro",
            "colorway": "Black/Dark Charcoal-Light Graphite",
            "style_code": "DH7138-006",
            "us_size": 9.5,
            "condition": "new",
            "box_included": True,
            "description": "Military Black 4s. Copped from SNKRS. Legit check available. Ships double boxed.",
            "seller": "sole_seller",
            "category_path": ("Sneakers", "Lifestyle", "Retro", "Low Top"),
            "start_price": 300.0,
            "reserve_price": 350.0,
            "bid_increment": 10.0,
            "close_time": current_time() + timedelta(days=6),
            "status": "open",
            "created_at": current_time() - timedelta(days=1),
        },
        {
            "title": "New Balance 990v5 Made in USA Grey",
            "brand": "New Balance",
            "model_name": "990v5",
            "colorway": "Grey/White",
            "style_code": "M990GL5",
            "us_size": 11.5,
            "condition": "like_new",
            "box_included": True,
            "description": "MiUSA 990v5 in classic grey. Worn 3 times. Perfect condition. Original box and extra laces.",
            "seller": "sneakerhead_nj",
            "category_path": ("Sneakers", "Performance", "Running", "Daily Trainer"),
            "start_price": 155.0,
            "reserve_price": 180.0,
            "bid_increment": 5.0,
            "close_time": current_time() + timedelta(days=8),
            "status": "open",
            "created_at": current_time() - timedelta(days=2),
        },
    ]

    sample_bids = [
        {
            "item_title": "Air Jordan 1 Retro High OG Chicago",
            "bidder": "sneakerhead_nj",
            "amount": 360.0,
            "placed_at": current_time() - timedelta(days=1),
        },
        {
            "item_title": "Air Jordan 1 Retro High OG Chicago",
            "bidder": "kicks_collector",
            "amount": 370.0,
            "placed_at": current_time() - timedelta(hours=12),
        },
        {
            "item_title": "Nike Dunk Low Panda",
            "bidder": "kicks_collector",
            "amount": 125.0,
            "placed_at": current_time() - timedelta(hours=10),
        },
    ]

    extra_sample_titles = [
        "Air Jordan 1 Retro High OG Lost and Found",
        "Nike Terminator High Georgetown",
        "Air Jordan 1 Retro High OG University Blue",
        "adidas Forum 84 High Royal Blue",
        "Air Jordan 1 Low OG Mocha",
        "Nike Air Force 1 Low Triple White",
        "New Balance 550 White Green",
        "Nike SB Dunk Low Pro Yuto Horigome",
        "adidas Campus 00s Core Black",
        "Puma Suede XL Black White",
        "Nike Kobe 6 Protro Reverse Grinch",
        "adidas AE 1 New Wave",
        "Puma MB.03 Toxic",
        "Air Jordan 38 Low Fundamental",
        "JJJJound x New Balance 991 Made in UK Grey Olive",
        "A Ma Maniere x Air Jordan 5 Dusk",
        "Kith x ASICS Gel-Lyte III Super Orange",
        "Nike Air Force 1 Low Linen Atmos",
        "ASICS Gel-Lyte III Tokyo",
        "Puma Palermo Tokyo",
        "Nike Air Force 1 Low Triple White",
        "Adidas Stan Smith White Green",
        "Nike Blazer Mid 77 Vintage White",
        "Asics Gel-Nimbus 25 Black",
        "Puma Suede Classic XXI Black",
        "Jordan 1 Mid Bred Toe",
        "Nike React Infinity Run 4 Blue",
        "Adidas Ultraboost 22 Triple Black",
        "Nike Dunk High Pro SB Baroque Brown",
        "Converse Chuck 70 High Top Parchment",
        "Nike Air Jordan 3 Retro White Cement",
        "New Balance 574 Grey Navy",
        "Adidas Forum Low White Blue",
        "Nike Air Max 270 React Black",
        "Vans Old Skool Black White",
        "Nike Air Force 1 Stussy Black",
        "Nike LeBron 21 Akoya",
        "Adidas Yeezy Boost 350 V2 Zebra",
        "Air Jordan 1 Retro High OG Bred Patent",
        "New Balance 990v6 Grey",
        "Asics Gel-Kayano 14 Cream Black",
    ]
    extra_sample_usernames = ["dwiti", "sinchana", "charvi", "anish"]

    try:
        sample_usernames = [spec["username"] for spec in sample_users] + extra_sample_usernames
        sample_titles = [spec["title"] for spec in sample_items] + extra_sample_titles

        existing_users = User.query.filter(User.username.in_(sample_usernames)).all()
        existing_user_ids = [user.id for user in existing_users]
        existing_items = Item.query.filter(Item.title.in_(sample_titles)).all()
        existing_item_ids = [item.id for item in existing_items]

        if existing_user_ids or existing_item_ids:
            existing_questions = Question.query.filter(
                (Question.user_id.in_(existing_user_ids or [-1])) | (Question.item_id.in_(existing_item_ids or [-1]))
            ).all()
            existing_question_ids = [question.id for question in existing_questions]

            Answer.query.filter(
                (Answer.rep_id.in_(existing_user_ids or [-1])) | (Answer.question_id.in_(existing_question_ids or [-1]))
            ).delete(synchronize_session=False)
            Notification.query.filter(Notification.user_id.in_(existing_user_ids or [-1])).delete(
                synchronize_session=False
            )
            Alert.query.filter(Alert.user_id.in_(existing_user_ids or [-1])).delete(synchronize_session=False)
            AutoBid.query.filter(
                (AutoBid.bidder_id.in_(existing_user_ids or [-1]))
                | (AutoBid.item_id.in_(existing_item_ids or [-1]))
            ).delete(synchronize_session=False)
            Bid.query.filter(
                (Bid.bidder_id.in_(existing_user_ids or [-1])) | (Bid.item_id.in_(existing_item_ids or [-1]))
            ).delete(synchronize_session=False)
            Question.query.filter(Question.id.in_(existing_question_ids or [-1])).delete(synchronize_session=False)
            Item.query.filter(Item.id.in_(existing_item_ids or [-1])).delete(synchronize_session=False)
            User.query.filter(User.id.in_(existing_user_ids or [-1])).delete(synchronize_session=False)
            db.session.flush()

        users_by_username = {}
        for spec in sample_users:
            user = User(
                username=spec["username"],
                email=spec["email"],
                password_hash=generate_password_hash(spec["password"]),
                role=spec["role"],
                is_active=True,
                created_at=spec["created_at"],
            )
            db.session.add(user)
            users_by_username[spec["username"]] = user

        db.session.flush()

        items_by_title = {}
        for spec in sample_items:
            category = get_category_by_path(spec["category_path"])
            if category is None:
                raise ValueError(f"Missing sample-data category path: {' > '.join(spec['category_path'])}")

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
                seller_id=users_by_username[spec["seller"]].id,
                category_id=category.id,
                start_price=spec["start_price"],
                reserve_price=spec["reserve_price"],
                bid_increment=spec["bid_increment"],
                close_time=spec["close_time"],
                status=spec["status"],
                created_at=spec["created_at"],
            )
            db.session.add(item)
            db.session.flush()
            items_by_title[spec["title"]] = item

        for spec in sample_bids:
            db.session.add(
                Bid(
                    item_id=items_by_title[spec["item_title"]].id,
                    bidder_id=users_by_username[spec["bidder"]].id,
                    amount=spec["amount"],
                    placed_at=spec["placed_at"],
                    is_auto=False,
                )
            )

        db.session.flush()

        db.session.add(
            AutoBid(
                item_id=items_by_title["Adidas Yeezy Boost 350 V2 Zebra"].id,
                bidder_id=users_by_username["jordan_fan"].id,
                upper_limit=400.0,
            )
        )

        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def parse_args():
    parser = argparse.ArgumentParser(
        description="Initialize required KicksBid reference data and database artifacts."
    )
    parser.add_argument("--admin-username")
    parser.add_argument("--admin-email")
    parser.add_argument("--admin-password")
    parser.add_argument("--load-samples", action="store_true", help="Load the demo SQL sample data")
    return parser.parse_args()


def main():
    args = parse_args()
    admin_values = [args.admin_username, args.admin_email, args.admin_password]

    if any(admin_values) and not all(admin_values):
        raise SystemExit(
            "Provide all admin fields together: --admin-username, --admin-email, and --admin-password."
        )

    with app.app_context():
        created_categories = bootstrap_categories()
        migrated_categories = migrate_legacy_categories()
        migrated_conditions = migrate_legacy_conditions()
        admin_username = (args.admin_username or os.getenv("ADMIN_USERNAME") or "admin").strip()
        admin_email = (args.admin_email or os.getenv("ADMIN_EMAIL") or "admin@kicksbid.local").strip()
        admin_password = args.admin_password or os.getenv("ADMIN_PASSWORD") or "admin12345"
        admin_result = bootstrap_admin(admin_username, admin_email, admin_password)

        db.session.commit()
        artifact_result = install_database_artifacts(db.engine)

        if created_categories:
            print("Initialized categories:")
            for category_name in created_categories:
                print(f"- {category_name}")
        else:
            print("Categories already initialized.")

        if migrated_categories:
            print("Migrated legacy categories:")
            for migration in migrated_categories:
                print(f"- {migration}")

        if migrated_conditions:
            print("Migrated legacy condition values:")
            for migration in migrated_conditions:
                print(f"- {migration}")

        created, admin = admin_result
        verb = "Created" if created else "Updated"
        print(f"{verb} admin account: {admin.username} ({admin.email})")

        if args.load_samples:
            try:
                load_sql_sample_data()
                print("Loaded custom SQL sample data successfully.")
            except Exception as e:
                print(f"Failed to load sample data: {e}")

        if artifact_result["skipped"]:
            print("Skipped database artifacts because the active database is not MySQL.")
        else:
            print(
                "Installed database artifacts: "
                f"{artifact_result['installed_check_constraints']} check constraints, "
                f"{artifact_result['installed_foreign_keys']} foreign keys, "
                f"{artifact_result['installed_indexes']} indexes, "
                f"{artifact_result['installed_functions']} functions, "
                f"{artifact_result['installed_views']} views, "
                f"{artifact_result['installed_procedures']} stored procedures, "
                f"{artifact_result['installed_triggers']} triggers, "
                f"{artifact_result['installed_events']} events."
            )
            if artifact_result["warnings"]:
                print("Warnings:")
                for warning in artifact_result["warnings"]:
                    print(f"- {warning}")


if __name__ == "__main__":
    main()
