import argparse
import os

from werkzeug.security import generate_password_hash

from app import app
from extensions import db
from models import Category, User


CATEGORY_TREE = {
    "Sneakers": [
        "Running",
        "Basketball",
        "Lifestyle",
        "Retro",
        "Collab / Limited",
    ]
}


def ensure_category(name, parent=None):
    parent_id = parent.id if parent else None
    category = Category.query.filter_by(name=name, parent_id=parent_id).first()
    if category is None:
        category = Category(name=name, parent_id=parent_id)
        db.session.add(category)
        db.session.flush()
    return category


def bootstrap_categories():
    created = []
    for root_name, children in CATEGORY_TREE.items():
        root = Category.query.filter_by(name=root_name, parent_id=None).first()
        if root is None:
            root = Category(name=root_name)
            db.session.add(root)
            db.session.flush()
            created.append(root_name)

        for child_name in children:
            existing_child = Category.query.filter_by(name=child_name, parent_id=root.id).first()
            if existing_child is None:
                db.session.add(Category(name=child_name, parent_id=root.id))
                created.append(f"{root_name} > {child_name}")

    return created


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
        description="Initialize required KicksBid reference data without creating sample marketplace activity."
    )
    parser.add_argument("--admin-username", default=os.getenv("ADMIN_USERNAME"))
    parser.add_argument("--admin-email", default=os.getenv("ADMIN_EMAIL"))
    parser.add_argument("--admin-password", default=os.getenv("ADMIN_PASSWORD"))
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
        admin_result = None

        if all(admin_values):
            admin_result = bootstrap_admin(
                args.admin_username.strip(),
                args.admin_email.strip(),
                args.admin_password,
            )

        db.session.commit()

        if created_categories:
            print("Initialized categories:")
            for category_name in created_categories:
                print(f"- {category_name}")
        else:
            print("Categories already initialized.")

        if admin_result is None:
            print("No admin account changes made.")
        else:
            created, admin = admin_result
            verb = "Created" if created else "Updated"
            print(f"{verb} admin account: {admin.username} ({admin.email})")


if __name__ == "__main__":
    main()
