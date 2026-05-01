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

    # Break your SQL script into individual executable statements
    queries = [
        """
        INSERT IGNORE INTO users (username, email, password_hash, role, is_active, created_at) VALUES
        ('jordan_fan', 'jordan@example.com', 'scrypt:32768:8:1$abc$hashedpw1', 'user', 1, NOW() - INTERVAL 30 DAY),
        ('sneakerhead_nj', 'sneaker@example.com', 'scrypt:32768:8:1$abc$hashedpw2', 'user', 1, NOW() - INTERVAL 25 DAY),
        ('kicks_collector', 'collector@example.com', 'scrypt:32768:8:1$abc$hashedpw3', 'user', 1, NOW() - INTERVAL 20 DAY),
        ('sole_seller', 'seller@example.com', 'scrypt:32768:8:1$abc$hashedpw4', 'user', 1, NOW() - INTERVAL 15 DAY),
        ('rep_mike', 'rep@kicksbid.local', 'scrypt:32768:8:1$abc$hashedpw5', 'rep', 1, NOW() - INTERVAL 60 DAY)
        """,
        "DROP TEMPORARY TABLE IF EXISTS tmp_cats",
        """
        CREATE TEMPORARY TABLE tmp_cats AS
        SELECT c4.id, CONCAT(c1.name, ' > ', c2.name, ' > ', c3.name, ' > ', c4.name) AS full_path
        FROM categories c1
        JOIN categories c2 ON c2.parent_id = c1.id
        JOIN categories c3 ON c3.parent_id = c2.id
        JOIN categories c4 ON c4.parent_id = c3.id
        """,
        """
        INSERT IGNORE INTO items (
          title, brand, model_name, colorway, style_code,
          us_size, condition, box_included, description,
          seller_id, category_id,
          start_price, reserve_price, bid_increment,
          close_time, status, created_at
        )
        SELECT
          'Air Jordan 1 Retro High OG Chicago',
          'Nike', 'Air Jordan 1 Retro High OG', 'White/Black-Varsity Red', '555088-101',
          10.5, 'new', 1,
          'Deadstock AJ1 Chicago colorway. Never worn, tried on once indoors. All tags attached. OG box included.',
          (SELECT id FROM users WHERE username = 'sole_seller'),
          (SELECT id FROM tmp_cats WHERE full_path = 'Sneakers > Lifestyle > Retro > High Top'),
          350.00, 400.00, 10.00,
          NOW() + INTERVAL 5 DAY, 'open', NOW() - INTERVAL 2 DAY
        UNION ALL SELECT
          'Nike Dunk Low Panda',
          'Nike', 'Dunk Low', 'White/Black', 'DD1391-100',
          9.0, 'like_new', 1,
          'Worn twice. No creasing. Box included. Classic Panda colorway that goes with everything.',
          (SELECT id FROM users WHERE username = 'jordan_fan'),
          (SELECT id FROM tmp_cats WHERE full_path = 'Sneakers > Lifestyle > Skate > Dunk-Inspired'),
          120.00, 140.00, 5.00,
          NOW() + INTERVAL 3 DAY, 'open', NOW() - INTERVAL 1 DAY
        UNION ALL SELECT
          'Adidas Yeezy Boost 350 V2 Zebra',
          'Adidas', 'Yeezy Boost 350 V2', 'White/Core Black/Red', 'CP9654',
          11.0, 'new', 1,
          'Brand new Zebra Yeezy. Purchased from Adidas confirmed app. 100% authentic with receipt.',
          (SELECT id FROM users WHERE username = 'sneakerhead_nj'),
          (SELECT id FROM tmp_cats WHERE full_path = 'Sneakers > Collector > Limited > Regional Exclusive'),
          280.00, 320.00, 10.00,
          NOW() + INTERVAL 7 DAY, 'open', NOW() - INTERVAL 3 DAY
        UNION ALL SELECT
          'Nike Air Max 90 Infrared',
          'Nike', 'Air Max 90', 'White/Black-Infrared', 'CT1685-100',
          10.0, 'good', 0,
          'OG AM90 Infrared. Light wear on outsole. Box not included. Cleaned and ready to ship.',
          (SELECT id FROM users WHERE username = 'kicks_collector'),
          (SELECT id FROM tmp_cats WHERE full_path = 'Sneakers > Lifestyle > Casual > Court Classic'),
          85.00, 100.00, 5.00,
          NOW() + INTERVAL 4 DAY, 'open', NOW() - INTERVAL 4 DAY
        UNION ALL SELECT
          'Jordan 4 Retro Military Black',
          'Nike', 'Air Jordan 4 Retro', 'Black/Dark Charcoal-Light Graphite', 'DH7138-006',
          9.5, 'new', 1,
          'Military Black 4s. Copped from SNKRS. Legit check available. Ships double boxed.',
          (SELECT id FROM users WHERE username = 'sole_seller'),
          (SELECT id FROM tmp_cats WHERE full_path = 'Sneakers > Lifestyle > Retro > Low Top'),
          300.00, 350.00, 10.00,
          NOW() + INTERVAL 6 DAY, 'open', NOW() - INTERVAL 1 DAY
        UNION ALL SELECT
          'New Balance 990v5 Made in USA Grey',
          'New Balance', '990v5', 'Grey/White', 'M990GL5',
          11.5, 'like_new', 1,
          'MiUSA 990v5 in classic grey. Worn 3 times. Perfect condition. Original box and extra laces.',
          (SELECT id FROM users WHERE username = 'sneakerhead_nj'),
          (SELECT id FROM tmp_cats WHERE full_path = 'Sneakers > Performance > Running > Daily Trainer'),
          155.00, 180.00, 5.00,
          NOW() + INTERVAL 8 DAY, 'open', NOW() - INTERVAL 2 DAY
        """,
        """
        INSERT INTO bids (item_id, bidder_id, amount, placed_at, is_auto)
        SELECT i.id, u.id, 360.00, NOW() - INTERVAL 1 DAY, 0
        FROM items i, users u
        WHERE i.title = 'Air Jordan 1 Retro High OG Chicago' AND u.username = 'sneakerhead_nj'
        """,
        """
        INSERT INTO bids (item_id, bidder_id, amount, placed_at, is_auto)
        SELECT i.id, u.id, 370.00, NOW() - INTERVAL 12 HOUR, 0
        FROM items i, users u
        WHERE i.title = 'Air Jordan 1 Retro High OG Chicago' AND u.username = 'kicks_collector'
        """,
        """
        INSERT INTO bids (item_id, bidder_id, amount, placed_at, is_auto)
        SELECT i.id, u.id, 125.00, NOW() - INTERVAL 10 HOUR, 0
        FROM items i, users u
        WHERE i.title = 'Nike Dunk Low Panda' AND u.username = 'kicks_collector'
        """,
        """
        INSERT INTO autobids (item_id, bidder_id, upper_limit)
        SELECT i.id, u.id, 400.00
        FROM items i, users u
        WHERE i.title = 'Adidas Yeezy Boost 350 V2 Zebra' AND u.username = 'jordan_fan'
        """,
        """
        INSERT INTO notifications (user_id, message, is_read, created_at)
        SELECT u.id, 'You have been outbid on Air Jordan 1 Retro High OG Chicago. Current bid: $370.00', 0, NOW() - INTERVAL 12 HOUR
        FROM users u WHERE u.username = 'sneakerhead_nj'
        """,
        """
        INSERT INTO notifications (user_id, message, is_read, created_at)
        SELECT u.id, 'Your listing "Nike Dunk Low Panda" received a new bid of $125.00!', 0, NOW() - INTERVAL 10 HOUR
        FROM users u WHERE u.username = 'jordan_fan'
        """,
        """
        INSERT INTO questions (user_id, item_id, body, created_at)
        SELECT u.id, i.id, 'Does the box have any damage? Also is the size US 10.5 or EU?', NOW() - INTERVAL 18 HOUR
        FROM users u, items i
        WHERE u.username = 'kicks_collector' AND i.title = 'Air Jordan 1 Retro High OG Chicago'
        """,
        """
        INSERT INTO answers (question_id, rep_id, body, created_at)
        SELECT q.id, u.id, 'The box is in excellent condition with minimal shelf wear. US 10.5 = EU 44.5.', NOW() - INTERVAL 15 HOUR
        FROM questions q, users u
        WHERE q.body LIKE '%Does the box have any damage%' AND u.username = 'rep_mike'
        """,
        """
        INSERT INTO alerts (user_id, category_id, keywords)
        SELECT u.id, c.id, 'Jordan retro'
        FROM users u, tmp_cats c
        WHERE u.username = 'sneakerhead_nj' AND c.full_path = 'Sneakers > Lifestyle > Retro > High Top'
        """,
        """
        INSERT INTO alerts (user_id, category_id, keywords)
        SELECT u.id, c.id, 'Yeezy'
        FROM users u, tmp_cats c
        WHERE u.username = 'kicks_collector' AND c.full_path = 'Sneakers > Collector > Limited > Regional Exclusive'
        """,
        "DROP TEMPORARY TABLE IF EXISTS tmp_cats"
    ]

    with db.engine.begin() as conn:
        for q in queries:
            conn.execute(text(q))


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
