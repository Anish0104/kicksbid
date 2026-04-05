from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.security import generate_password_hash

from extensions import db
from models import Answer, Bid, Item, Question, User

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


@admin_bp.route("/dashboard")
@login_required
@admin_required
def dashboard():
    total_bids = Bid.query.count()
    total_volume = db.session.query(db.func.sum(Bid.amount)).scalar() or 0
    open_auctions = Item.query.filter_by(status="open").count()
    top_items = (
        db.session.query(Item, db.func.max(Bid.amount).label("top_bid"))
        .join(Bid)
        .group_by(Item.id)
        .order_by(db.text("top_bid DESC"))
        .limit(5)
        .all()
    )
    top_buyers = (
        db.session.query(User, db.func.count(Bid.id).label("bid_count"))
        .join(Bid)
        .group_by(User.id)
        .order_by(db.text("bid_count DESC"))
        .limit(5)
        .all()
    )
    reps = User.query.filter_by(role="rep").order_by(User.username.asc()).all()
    return render_template(
        "admin/dashboard.html",
        total_bids=total_bids,
        total_volume=total_volume,
        open_auctions=open_auctions,
        top_items=top_items,
        top_buyers=top_buyers,
        reps=reps,
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


@admin_bp.route("/rep")
@login_required
@rep_required
def rep():
    questions = Question.query.order_by(Question.created_at.desc()).all()
    users = User.query.filter_by(role="user").order_by(User.username.asc()).all()
    bids = Bid.query.order_by(Bid.placed_at.desc()).limit(25).all()
    items = Item.query.order_by(Item.created_at.desc()).limit(25).all()
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
    return redirect(url_for("admin.rep"))


@admin_bp.route("/rep/remove-bid", methods=["POST"])
@login_required
@rep_required
def remove_bid():
    bid_id = request.form.get("bid_id", type=int)
    if not bid_id:
        flash("Bid ID is required.", "error")
        return redirect(url_for("admin.rep"))

    bid = db.get_or_404(Bid, bid_id)
    db.session.delete(bid)
    db.session.commit()
    flash("Bid removed.", "success")
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

    if username:
        user.username = username
    if email:
        user.email = email
    if password:
        user.password_hash = generate_password_hash(password)

    db.session.commit()
    flash("User updated.", "success")
    return redirect(url_for("admin.rep"))
