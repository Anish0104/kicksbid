import argparse
import os

from werkzeug.security import generate_password_hash

from app import app
from db_artifacts import install_database_artifacts
from extensions import db
from models import Alert, Category, Item, User


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


def parse_args():
    parser = argparse.ArgumentParser(
        description="Initialize required KicksBid reference data and database artifacts."
    )
    parser.add_argument("--admin-username")
    parser.add_argument("--admin-email")
    parser.add_argument("--admin-password")
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
