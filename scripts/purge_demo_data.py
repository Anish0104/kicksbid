import argparse
import sys
from pathlib import Path

from sqlalchemy import delete, or_, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import app
from extensions import db
from models import Answer, Alert, AutoBid, Bid, Item, Notification, Question, User


DEFAULT_SAMPLE_EMAILS = {
    "alice@test.com",
    "bob@test.com",
    "cam@test.com",
    "nina@test.com",
    "sarah@kicksbid.com",
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Remove legacy demo/sample marketplace data from the live KicksBid database."
    )
    parser.add_argument(
        "--include-default-admin",
        action="store_true",
        help="Also remove the old default admin account at admin@kicksbid.com.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without committing changes.",
    )
    return parser.parse_args()


def fetch_ids(statement):
    return list(db.session.execute(statement).scalars())


def main():
    args = parse_args()
    sample_emails = set(DEFAULT_SAMPLE_EMAILS)
    if args.include_default_admin:
        sample_emails.add("admin@kicksbid.com")

    with app.app_context():
        user_ids = fetch_ids(select(User.id).where(User.email.in_(sample_emails)))

        if not user_ids:
            print("No legacy sample users found.")
            return

        item_ids = fetch_ids(select(Item.id).where(Item.seller_id.in_(user_ids)))
        question_ids = fetch_ids(
            select(Question.id).where(
                or_(Question.user_id.in_(user_ids), Question.item_id.in_(item_ids or [-1]))
            )
        )

        counts = {
            "users": len(user_ids),
            "items": len(item_ids),
            "questions": len(question_ids),
            "answers": db.session.scalar(
                select(db.func.count(Answer.id)).where(
                    or_(Answer.rep_id.in_(user_ids), Answer.question_id.in_(question_ids or [-1]))
                )
            )
            or 0,
            "alerts": db.session.scalar(select(db.func.count(Alert.id)).where(Alert.user_id.in_(user_ids))) or 0,
            "notifications": db.session.scalar(
                select(db.func.count(Notification.id)).where(Notification.user_id.in_(user_ids))
            )
            or 0,
            "autobids": db.session.scalar(
                select(db.func.count(AutoBid.id)).where(
                    or_(AutoBid.bidder_id.in_(user_ids), AutoBid.item_id.in_(item_ids or [-1]))
                )
            )
            or 0,
            "bids": db.session.scalar(
                select(db.func.count(Bid.id)).where(
                    or_(Bid.bidder_id.in_(user_ids), Bid.item_id.in_(item_ids or [-1]))
                )
            )
            or 0,
        }

        print("Legacy sample records found:")
        for table_name, count in counts.items():
            print(f"- {table_name}: {count}")

        if args.dry_run:
            print("Dry run only. No changes committed.")
            return

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

        print("Legacy sample data removed.")


if __name__ == "__main__":
    main()
