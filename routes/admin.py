from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm import selectinload
from werkzeug.security import generate_password_hash

from extensions import db
from models import Alert, Answer, AutoBid, Bid, Item, Notification, Question, User
from time_utils import current_time

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "admin":
            flash("Admin access required.", "error")
            return redirect(url_for("search.browse"))
        return view(*args, **kwargs)

    return wrapped


def rep_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in {"admin", "rep"}:
            flash("Access denied.", "error")
            return redirect(url_for("search.browse"))
        return view(*args, **kwargs)

    return wrapped


def get_winning_bid(item):
    if not item.bids:
        return None
    return sorted(item.bids, key=lambda bid: (-bid.amount, bid.placed_at, bid.id))[0]


def build_sales_report():
    sold_items = (
        Item.query.options(
            selectinload(Item.seller),
            selectinload(Item.category),
            selectinload(Item.bids).selectinload(Bid.bidder),
        )
        .filter(Item.status == "closed")
        .order_by(Item.close_time.desc())
        .all()
    )

    sales_rows = []
    category_totals = {}
    seller_totals = {}
    buyer_totals = {}

    for item in sold_items:
        winning_bid = get_winning_bid(item)
        if winning_bid is None:
            continue

        row = {
            "item": item,
            "category_name": item.category.name if item.category else "Uncategorized",
            "seller": item.seller,
            "buyer": winning_bid.bidder,
            "final_price": winning_bid.amount,
            "close_time": item.close_time,
        }
        sales_rows.append(row)

        category_totals[row["category_name"]] = category_totals.get(row["category_name"], 0) + row["final_price"]
        seller_totals[row["seller"].id] = seller_totals.get(
            row["seller"].id,
            {"user": row["seller"], "total": 0.0, "sales_count": 0},
        )
        seller_totals[row["seller"].id]["total"] += row["final_price"]
        seller_totals[row["seller"].id]["sales_count"] += 1

        buyer_totals[row["buyer"].id] = buyer_totals.get(
            row["buyer"].id,
            {"user": row["buyer"], "total": 0.0, "wins": 0},
        )
        buyer_totals[row["buyer"].id]["total"] += row["final_price"]
        buyer_totals[row["buyer"].id]["wins"] += 1

    earnings_by_category = [
        {"name": name, "total": total}
        for name, total in sorted(category_totals.items(), key=lambda entry: entry[1], reverse=True)
    ]
    earnings_by_seller = sorted(seller_totals.values(), key=lambda entry: entry["total"], reverse=True)
    buyer_rankings = sorted(buyer_totals.values(), key=lambda entry: entry["total"], reverse=True)
    best_selling_items = sorted(sales_rows, key=lambda row: row["final_price"], reverse=True)[:5]

    total_earnings = sum(row["final_price"] for row in sales_rows)
    return {
        "total_earnings": total_earnings,
        "total_sales_count": len(sales_rows),
        "average_sale_price": total_earnings / len(sales_rows) if sales_rows else 0,
        "earnings_per_item": sales_rows,
        "earnings_by_category": earnings_by_category,
        "earnings_by_seller": earnings_by_seller,
        "best_selling_items": best_selling_items,
        "best_buyers": buyer_rankings[:5],
    }


@admin_bp.route("/dashboard")
@login_required
@admin_required
def dashboard():
    now = current_time()
    total_users = User.query.count()
    unanswered_questions_count = Question.query.filter(~Question.answers.any()).count()
    total_bids = Bid.query.count()
    active_auctions = Item.query.filter(Item.status == "open", Item.close_time > now).count()
    recent_bids = (
        Bid.query.options(selectinload(Bid.item), selectinload(Bid.bidder))
        .order_by(Bid.placed_at.desc())
        .limit(20)
        .all()
    )
    users = User.query.order_by(User.username.asc()).all()
    unanswered_questions = (
        Question.query.options(selectinload(Question.item), selectinload(Question.user))
        .filter(~Question.answers.any())
        .order_by(Question.created_at.desc())
        .all()
    )
    report = build_sales_report()

    return render_template(
        "admin/dashboard.html",
        total_users=total_users,
        active_auctions=active_auctions,
        total_bids=total_bids,
        unanswered_questions_count=unanswered_questions_count,
        recent_bids=recent_bids,
        users=users,
        unanswered_questions=unanswered_questions,
        report=report,
    )


@admin_bp.route("/create-rep", methods=["POST"])
@login_required
@admin_required
def create_rep():
    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not username or not email or not password:
        flash("All fields are required.", "error")
        return redirect(url_for("admin.dashboard"))

    if User.query.filter((User.username == username) | (User.email == email)).first():
        flash("Rep username or email already exists.", "error")
        return redirect(url_for("admin.dashboard"))

    rep = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
        role="rep",
    )
    db.session.add(rep)
    db.session.commit()
    flash(f"Rep account created for {username}.", "success")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/promote/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def promote_user(user_id):
    user = db.get_or_404(User, user_id)
    if user.role == "admin":
        flash("Admin users already have elevated access.", "error")
        return redirect(url_for("admin.dashboard"))

    if user.role == "rep":
        flash(f"{user.username} is already a rep.", "error")
        return redirect(url_for("admin.dashboard"))

    user.role = "rep"
    db.session.commit()
    flash(f"{user.username} has been promoted to rep.", "success")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/rep")
@login_required
@rep_required
def rep():
    questions = (
        Question.query.options(
            selectinload(Question.user),
            selectinload(Question.item),
            selectinload(Question.answers).selectinload(Answer.rep),
        )
        .order_by(Question.created_at.desc())
        .all()
    )
    users = User.query.filter(User.role.in_(["user", "deleted"])).order_by(User.username.asc()).all()
    bids = (
        Bid.query.options(selectinload(Bid.bidder), selectinload(Bid.item))
        .order_by(Bid.placed_at.desc())
        .limit(25)
        .all()
    )
    items = (
        Item.query.options(selectinload(Item.seller), selectinload(Item.category))
        .order_by(Item.created_at.desc())
        .limit(25)
        .all()
    )
    return render_template("admin/rep.html", questions=questions, users=users, bids=bids, items=items)


@admin_bp.route("/rep/answer/<int:question_id>", methods=["POST"])
@login_required
@rep_required
def answer_question(question_id):
    body = request.form.get("body", "").strip()
    if body:
        db.session.add(Answer(question_id=question_id, rep_id=current_user.id, body=body))
        db.session.commit()
        flash("Answer posted.", "success")

    next_target = request.args.get("next", "").strip()
    if next_target == "dashboard" and current_user.role == "admin":
        return redirect(url_for("admin.dashboard"))
    return redirect(url_for("admin.rep"))


@admin_bp.route("/rep/remove-bid", methods=["POST"])
@login_required
@rep_required
def remove_bid():
    bid_id = request.form.get("bid_id", type=int)
    if not bid_id:
        flash("Bid ID is required.", "error")
        return redirect(url_for("admin.rep"))

    from routes.auctions import recalculate_item_status, restore_autobid_visibility

    bid = db.get_or_404(Bid, bid_id)
    item = bid.item
    db.session.delete(bid)
    db.session.flush()
    restore_autobid_visibility(item)
    recalculate_item_status(item)
    db.session.commit()
    flash("Bid removed and auction state recomputed.", "success")
    return redirect(url_for("admin.rep"))


@admin_bp.route("/rep/remove-auction", methods=["POST"])
@login_required
@rep_required
def remove_auction():
    item_id = request.form.get("item_id", type=int)
    if not item_id:
        flash("Auction ID is required.", "error")
        return redirect(url_for("admin.rep"))

    item = db.get_or_404(Item, item_id)
    item.status = "removed"
    db.session.commit()
    flash("Auction removed.", "success")
    return redirect(url_for("admin.rep"))


@admin_bp.route("/rep/edit-user", methods=["POST"])
@login_required
@rep_required
def edit_user():
    user_id = request.form.get("user_id", type=int)
    if not user_id:
        flash("User ID is required.", "error")
        return redirect(url_for("admin.rep"))

    user = db.get_or_404(User, user_id)
    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if username and User.query.filter(User.username == username, User.id != user.id).first():
        flash("That username is already in use.", "error")
        return redirect(url_for("admin.rep"))

    if email and User.query.filter(User.email == email, User.id != user.id).first():
        flash("That email is already in use.", "error")
        return redirect(url_for("admin.rep"))

    if username:
        user.username = username
    if email:
        user.email = email
    if password:
        user.password_hash = generate_password_hash(password)

    db.session.commit()
    flash("User updated.", "success")
    return redirect(url_for("admin.rep"))


@admin_bp.route("/rep/delete-user", methods=["POST"])
@login_required
@rep_required
def delete_user():
    user_id = request.form.get("user_id", type=int)
    if not user_id:
        flash("User ID is required.", "error")
        return redirect(url_for("admin.rep"))

    user = db.get_or_404(User, user_id)
    if user.role == "admin":
        flash("Admin accounts cannot be deleted from rep tools.", "error")
        return redirect(url_for("admin.rep"))

    for item in Item.query.filter_by(seller_id=user.id, status="open").all():
        item.status = "removed"

    AutoBid.query.filter_by(bidder_id=user.id).delete()
    Alert.query.filter_by(user_id=user.id).delete()
    Notification.query.filter_by(user_id=user.id).delete()

    user.is_active = False
    user.role = "deleted"
    user.username = f"deleted-user-{user.id}"
    user.email = f"deleted-{user.id}@kicksbid.local"

    db.session.commit()
    flash("User account deactivated.", "success")
    return redirect(url_for("admin.rep"))


@admin_bp.route("/rep/edit-auction", methods=["POST"])
@login_required
@rep_required
def edit_auction():
    item_id = request.form.get("item_id", type=int)
    if not item_id:
        flash("Auction ID is required.", "error")
        return redirect(url_for("admin.rep"))

    item = db.get_or_404(Item, item_id)
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    status = request.form.get("status", "").strip()
    close_time_raw = request.form.get("close_time", "").strip()
    reserve_price = request.form.get("reserve_price", "").strip()
    bid_increment = request.form.get("bid_increment", "").strip()

    if title:
        item.title = title
    if description:
        item.description = description
    if status in {"open", "closed", "no_winner", "removed"}:
        item.status = status
    if close_time_raw:
        try:
            item.close_time = datetime.strptime(close_time_raw, "%Y-%m-%dT%H:%M")
        except ValueError:
            flash("Invalid close time format.", "error")
            return redirect(url_for("admin.rep"))
    if reserve_price:
        try:
            item.reserve_price = float(reserve_price)
        except ValueError:
            flash("Reserve price must be numeric.", "error")
            return redirect(url_for("admin.rep"))
    if bid_increment:
        try:
            item.bid_increment = float(bid_increment)
        except ValueError:
            flash("Bid increment must be numeric.", "error")
            return redirect(url_for("admin.rep"))

    db.session.commit()
    flash("Auction updated.", "success")
    return redirect(url_for("admin.rep"))
