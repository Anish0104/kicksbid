from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from models import Alert, AutoBid, Bid, Item, Notification, User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("search.browse"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not username or not email or not password:
            flash("All fields are required.", "error")
            return render_template("auth/register.html")

        if User.query.filter_by(username=username).first():
            flash("Username already taken.", "error")
            return render_template("auth/register.html")

        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "error")
            return render_template("auth/register.html")

        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            role="user",
        )
        db.session.add(user)
        db.session.commit()
        flash("Account created. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("search.browse"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            if not user.is_active:
                flash("This account has been deleted or deactivated.", "error")
                return render_template("auth/login.html")

            login_user(user)
            if user.role == "admin":
                return redirect(url_for("admin.dashboard"))
            if user.role == "rep":
                return redirect(url_for("admin.rep"))
            return redirect(url_for("search.browse"))

        flash("Invalid username or password.", "error")

    return render_template("auth/login.html")


@auth_bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@auth_bp.route("/account")
@login_required
def account():
    return render_template(
        "auth/account.html",
        active_auctions_count=Item.query.filter_by(seller_id=current_user.id, status="open").count(),
        total_listings_count=Item.query.filter_by(seller_id=current_user.id).count(),
        total_bids_count=Bid.query.filter_by(bidder_id=current_user.id).count(),
        autobid_count=AutoBid.query.filter_by(bidder_id=current_user.id).count(),
        alert_count=Alert.query.filter_by(user_id=current_user.id).count(),
        unread_notifications_count=Notification.query.filter_by(
            user_id=current_user.id,
            is_read=False,
        ).count(),
    )


@auth_bp.route("/account/delete", methods=["POST"])
@login_required
def delete_account():
    if current_user.role != "user":
        flash("Only end-user accounts can be deleted from this page.", "error")
        return redirect(url_for("auth.account"))

    user = db.session.get(User, current_user.id)

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
    logout_user()
    flash("Your account has been deleted and your active listings were removed.", "success")
    return redirect(url_for("landing"))
