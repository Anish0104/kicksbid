import os

from flask import Flask, render_template
from flask_login import current_user
from extensions import db, login_manager
from sqlalchemy import inspect, text
from sqlalchemy.orm import joinedload
from time_utils import current_time

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "kicksbid-secret-2024")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://root:anish08032003@localhost/kicksbid",
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024


db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = "auth.login"


@login_manager.user_loader
def load_user(user_id):
    from models import User

    return db.session.get(User, int(user_id))


with app.app_context():
    from models import User, Category, Item, Bid, AutoBid, Alert, Question, Answer, Notification

    db.create_all()

    inspector = inspect(db.engine)
    item_columns = {column["name"]: column for column in inspector.get_columns("items")}
    if "image_url_override" not in item_columns:
        db.session.execute(text("ALTER TABLE items ADD COLUMN image_url_override VARCHAR(500)"))
        db.session.commit()
    else:
        image_column_type = str(item_columns["image_url_override"]["type"]).lower()
        if "text" not in image_column_type:
            db.session.execute(text("ALTER TABLE items MODIFY COLUMN image_url_override TEXT"))
            db.session.commit()
    if "image_data" not in item_columns:
        db.session.execute(text("ALTER TABLE items ADD COLUMN image_data LONGBLOB NULL"))
        db.session.commit()

os.makedirs(os.path.join(app.root_path, "static", "uploads", "items"), exist_ok=True)
app.config["ITEM_UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "uploads", "items")


def format_time_left(close_time, now):
    remaining_seconds = max(int((close_time - now).total_seconds()), 0)
    days, remainder = divmod(remaining_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = max(remainder // 60, 1)

    if days:
        return f"{days}d {hours}h left"
    if hours:
        return f"{hours}h {minutes}m left"
    return f"{minutes}m left"


def build_landing_context():
    from models import Bid, Item, User

    now = current_time()
    bid_summary = (
        db.session.query(
            Bid.item_id.label("item_id"),
            db.func.max(Bid.amount).label("current_bid"),
            db.func.count(Bid.id).label("bid_count"),
        )
        .group_by(Bid.item_id)
        .subquery()
    )

    featured_rows = (
        db.session.query(Item, bid_summary.c.current_bid, bid_summary.c.bid_count)
        .options(joinedload(Item.seller), joinedload(Item.category))
        .outerjoin(bid_summary, bid_summary.c.item_id == Item.id)
        .filter(Item.status == "open", Item.close_time > now)
        .order_by(Item.close_time.asc(), Item.created_at.desc())
        .limit(6)
        .all()
    )

    featured_items = []
    for item, current_bid, bid_count in featured_rows:
        featured_items.append(
            {
                "item": item,
                "current_bid": current_bid or item.start_price,
                "bid_count": int(bid_count or 0),
                "time_left": format_time_left(item.close_time, now),
            }
        )

    return {
        "featured_items": featured_items,
        "active_auctions": Item.query.filter(Item.status == "open", Item.close_time > now).count(),
        "collector_count": User.query.filter(
            User.role == "user",
            User.is_active.is_(True),
        ).count(),
        "total_bids": Bid.query.count(),
    }


@app.before_request
def sync_expired_auctions():
    from routes.auctions import close_expired_auctions

    close_expired_auctions()


@app.context_processor
def inject_global_state():
    if not current_user.is_authenticated:
        return {"saved_alert_count": 0, "unread_notifications_count": 0}

    from models import Alert, Notification

    return {
        "saved_alert_count": Alert.query.filter_by(user_id=current_user.id).count(),
        "unread_notifications_count": Notification.query.filter_by(
            user_id=current_user.id,
            is_read=False,
        ).count(),
    }


@app.route("/")
@app.route("/landing")
def landing():
    return render_template("landing.html", **build_landing_context())


from routes.auth import auth_bp
from routes.auctions import auctions_bp
from routes.search import search_bp
from routes.admin import admin_bp

app.register_blueprint(auth_bp)
app.register_blueprint(auctions_bp)
app.register_blueprint(search_bp)
app.register_blueprint(admin_bp)


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5001"))
    debug = os.getenv("FLASK_DEBUG", "1") == "1"
    app.run(host=host, port=port, debug=debug)
