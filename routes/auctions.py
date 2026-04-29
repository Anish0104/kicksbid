from io import BytesIO
from datetime import datetime, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload
from werkzeug.utils import secure_filename

from extensions import db
from image_utils import build_item_cutout, build_processed_item_filename
from models import Alert, Answer, AutoBid, Bid, Category, Item, Notification, Question, User
from time_utils import current_time

auctions_bp = Blueprint("auctions", __name__, url_prefix="/auctions")
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}


def ensure_end_user():
    if current_user.role != "user":
        flash("Only end-user accounts can use this feature.", "error")
        return False
    return True


def ensure_listing_seller():
    if current_user.role not in {"user", "admin"}:
        flash("Only seller or admin accounts can create auctions.", "error")
        return False
    return True


def get_leaf_categories():
    categories = Category.query.filter(~Category.subcategories.any()).all()
    return sorted(categories, key=lambda category: category.full_name.lower())


def build_listing_form_values(selected_category=None):
    default_category = str(selected_category) if selected_category else ""
    return {
        "title": request.form.get("title", "").strip(),
        "brand": request.form.get("brand", "").strip(),
        "model_name": request.form.get("model_name", "").strip(),
        "colorway": request.form.get("colorway", "").strip(),
        "style_code": request.form.get("style_code", "").strip(),
        "us_size": request.form.get("us_size", "").strip(),
        "condition": request.form.get("condition", "new").strip().lower(),
        "category_id": request.form.get("category_id", default_category),
        "box_included": request.form.get("box_included", "on") == "on",
        "description": request.form.get("description", "").strip(),
        "start_price": request.form.get("start_price", "").strip(),
        "reserve_price": request.form.get("reserve_price", "").strip(),
        "bid_increment": request.form.get("bid_increment", "").strip(),
        "close_time": request.form.get("close_time", "").strip(),
    }


def render_create_form(categories, selected_category=None):
    return render_template(
        "auctions/create.html",
        categories=categories,
        selected_category=selected_category,
        form_values=build_listing_form_values(selected_category),
    )


def save_uploaded_item_image(image_file):
    filename = secure_filename(image_file.filename or "")
    if not filename:
        return None, "Please choose a valid image file."

    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_IMAGE_EXTENSIONS))
        return None, f"Image must be one of: {allowed}."

    try:
        image_file.stream.seek(0)
        processed_image = build_item_cutout(image_file.stream)
    except Exception:
        return None, "We could not process that image. Please upload a clear sneaker photo in JPG, PNG, WEBP, or GIF format."

    output = BytesIO()
    processed_image.save(output, format="PNG")
    output.seek(0)
    return output.read(), None


def get_leading_bid(item_id, for_update=False):
    query = Bid.query.filter_by(item_id=item_id).order_by(Bid.amount.desc(), Bid.placed_at.asc(), Bid.id.asc())
    if for_update:
        query = query.with_for_update()
    return query.first()


def get_locked_item_or_404(item_id):
    item = Item.query.filter_by(id=item_id).with_for_update().first()
    if item is None:
        abort(404)
    return item


def get_current_bid(item):
    leading_bid = get_leading_bid(item.id)
    return leading_bid.amount if leading_bid else item.start_price


def get_item_participant_ids(item_id):
    bid_participants = {bidder_id for (bidder_id,) in db.session.query(Bid.bidder_id).filter_by(item_id=item_id).all()}
    autobid_participants = {
        bidder_id for (bidder_id,) in db.session.query(AutoBid.bidder_id).filter_by(item_id=item_id).all()
    }
    return bid_participants | autobid_participants


def add_notification(user_id, message):
    db.session.add(Notification(user_id=user_id, message=message))


def item_matches_alert(item, alert):
    if alert.category_id and alert.category_id != item.category_id:
        return False

    keywords = (alert.keywords or "").strip().lower()
    if not keywords:
        return True

    searchable_text = " ".join(
        [
            item.title,
            item.brand,
            item.model_name,
            item.colorway,
            item.style_code,
            item.description,
            f"{item.us_size:g}",
            f"size {item.us_size:g}",
        ]
    ).lower()
    tokens = [token for token in keywords.split() if token]
    return all(token in searchable_text for token in tokens)


def close_auction(item, commit=True):
    leading_bid = get_leading_bid(item.id)

    if not leading_bid or leading_bid.amount < item.reserve_price:
        item.status = "no_winner"
        add_notification(item.seller_id, f"{item.title} ended without meeting the reserve price.")
        losing_bidder_ids = {bid.bidder_id for bid in item.bids}
        for bidder_id in losing_bidder_ids:
            add_notification(bidder_id, f"{item.title} closed without a winner because the reserve was not met.")
    else:
        item.status = "closed"
        add_notification(
            leading_bid.bidder_id,
            f"Congratulations! You won {item.title} with a bid of ${leading_bid.amount:.2f}.",
        )
        if item.seller_id != leading_bid.bidder_id:
            add_notification(
                item.seller_id,
                f"Your auction for {item.title} sold for ${leading_bid.amount:.2f}.",
            )

    AutoBid.query.filter_by(item_id=item.id).delete()

    if commit:
        db.session.commit()


def close_expired_auctions():
    expired_items = Item.query.filter(Item.status == "open", Item.close_time <= current_time()).all()
    if not expired_items:
        return 0

    for item in expired_items:
        close_auction(item, commit=False)

    db.session.commit()
    return len(expired_items)


def maybe_close_item(item):
    if item.status == "open" and item.close_time <= current_time():
        close_auction(item)


def recalculate_item_status(item):
    if item.status == "removed":
        return

    leading_bid = get_leading_bid(item.id)
    if item.close_time > current_time():
        item.status = "open"
    elif leading_bid and leading_bid.amount >= item.reserve_price:
        item.status = "closed"
    else:
        item.status = "no_winner"


def restore_autobid_visibility(item):
    Bid.query.filter_by(item_id=item.id, is_auto=True).delete()
    db.session.flush()

    leading_bid = get_leading_bid(item.id)

    if leading_bid is None:
        leading_autobid = (
            AutoBid.query.filter_by(item_id=item.id)
            .order_by(AutoBid.upper_limit.desc(), AutoBid.id.asc())
            .first()
        )
        if leading_autobid is not None:
            opening_amount = min(item.start_price + item.bid_increment, leading_autobid.upper_limit)
            db.session.add(
                Bid(
                    item_id=item.id,
                    bidder_id=leading_autobid.bidder_id,
                    amount=opening_amount,
                    is_auto=True,
                )
            )
            db.session.flush()
            resolve_autobids(item, last_bid_amount=opening_amount, last_bidder_id=leading_autobid.bidder_id)
    else:
        resolve_autobids(item, last_bid_amount=leading_bid.amount, last_bidder_id=leading_bid.bidder_id)


def resolve_autobids(item, last_bid_amount=None, last_bidder_id=None):
    placed_auto_bids = []

    while True:
        leading_bid = get_leading_bid(item.id)
        if leading_bid is None:
            break

        minimum_response = leading_bid.amount + item.bid_increment
        candidate = (
            AutoBid.query.filter_by(item_id=item.id)
            .filter(AutoBid.bidder_id != leading_bid.bidder_id, AutoBid.upper_limit >= minimum_response)
            .order_by(AutoBid.upper_limit.desc(), AutoBid.id.asc())
            .first()
        )

        if candidate is None:
            break

        next_amount = min(minimum_response, candidate.upper_limit)
        if next_amount <= leading_bid.amount:
            break

        auto_bid = Bid(
            item_id=item.id,
            bidder_id=candidate.bidder_id,
            amount=next_amount,
            is_auto=True,
        )
        db.session.add(auto_bid)
        db.session.flush()
        placed_auto_bids.append(auto_bid)

    return placed_auto_bids


def notify_bid_activity(item, previous_leader_id):
    leading_bid = get_leading_bid(item.id)
    if leading_bid is None:
        return leading_bid

    final_amount = leading_bid.amount
    autobid_limits = {
        autobid.bidder_id: autobid.upper_limit
        for autobid in AutoBid.query.filter_by(item_id=item.id).all()
    }

    for participant_id in sorted(get_item_participant_ids(item.id)):
        if participant_id in {item.seller_id, leading_bid.bidder_id}:
            continue

        upper_limit = autobid_limits.get(participant_id)
        if upper_limit is not None and upper_limit < final_amount:
            add_notification(
                participant_id,
                f"A bid on {item.title} exceeded your auto-bid limit of ${upper_limit:.2f}.",
            )
        elif participant_id == previous_leader_id:
            add_notification(
                participant_id,
                f"You have been outbid on {item.title}. New highest bid: ${final_amount:.2f}.",
            )
        else:
            add_notification(
                participant_id,
                f"A higher bid was placed on {item.title}. New highest bid: ${final_amount:.2f}.",
            )

    if item.seller_id != leading_bid.bidder_id:
        add_notification(item.seller_id, f"New highest bid on {item.title}: ${final_amount:.2f}.")

    return leading_bid


def build_similar_items(item, limit=5):
    now = current_time()
    window_start = now - timedelta(days=30)
    candidates = (
        Item.query.options(selectinload(Item.seller), selectinload(Item.category), selectinload(Item.bids))
        .filter(
            Item.id != item.id,
            Item.category_id == item.category_id,
            Item.close_time >= window_start,
            Item.close_time <= now,
            Item.status.in_(["closed", "no_winner"]),
        )
        .all()
    )

    similar_items = []
    item_color_tokens = {token for token in item.colorway.lower().replace("/", " ").split() if len(token) > 2}

    for candidate in candidates:
        score = 2
        if candidate.brand.lower() == item.brand.lower():
            score += 3
        if candidate.model_name.lower() == item.model_name.lower():
            score += 3
        if candidate.condition == item.condition:
            score += 1
        if abs(candidate.us_size - item.us_size) <= 1:
            score += 1

        candidate_tokens = {
            token for token in candidate.colorway.lower().replace("/", " ").split() if len(token) > 2
        }
        if item_color_tokens & candidate_tokens:
            score += 1

        similar_items.append(
            {
                "item": candidate,
                "score": score,
                "final_bid": get_current_bid(candidate),
            }
        )

    similar_items.sort(
        key=lambda row: (
            -row["score"],
            -row["item"].close_time.timestamp(),
            -row["final_bid"],
        )
    )
    return similar_items[:limit]


@auctions_bp.route("/<int:item_id>")
def item_detail(item_id):
    item = db.get_or_404(Item, item_id)
    maybe_close_item(item)

    bids = (
        Bid.query.options(selectinload(Bid.bidder))
        .filter_by(item_id=item_id)
        .order_by(Bid.amount.desc(), Bid.placed_at.desc(), Bid.id.desc())
        .all()
    )
    questions = (
        Question.query.options(
            selectinload(Question.user),
            selectinload(Question.answers).selectinload(Answer.rep),
        )
        .filter_by(item_id=item_id)
        .order_by(Question.created_at.desc())
        .all()
    )

    can_view_reserve = current_user.is_authenticated and (
        current_user.id == item.seller_id or current_user.role in {"admin", "rep"}
    )

    return render_template(
        "auctions/item_detail.html",
        item=item,
        bids=bids,
        current_bid=get_current_bid(item),
        questions=questions,
        can_view_reserve=can_view_reserve,
        similar_items=build_similar_items(item),
    )


@auctions_bp.route("/<int:item_id>/image")
def item_image(item_id):
    item = db.get_or_404(Item, item_id)
    if not item.image_data:
        abort(404)

    return send_file(
        BytesIO(item.image_data),
        mimetype="image/png",
        download_name=build_processed_item_filename(item.title or f"item-{item.id}"),
        max_age=300,
    )


@auctions_bp.route("/<int:item_id>/bid", methods=["POST"])
@login_required
def place_bid(item_id):
    if not ensure_end_user():
        return redirect(url_for("auctions.item_detail", item_id=item_id))

    try:
        amount = float(request.form.get("amount", ""))
    except ValueError:
        flash("Invalid bid amount.", "error")
        return redirect(url_for("auctions.item_detail", item_id=item_id))

    try:
        item = get_locked_item_or_404(item_id)

        if item.status == "open" and item.close_time <= current_time():
            close_auction(item, commit=False)

        if item.status != "open":
            db.session.commit()
            flash("This auction is no longer open.", "error")
            return redirect(url_for("auctions.item_detail", item_id=item_id))

        if current_user.id == item.seller_id:
            db.session.rollback()
            flash("You cannot bid on your own auction.", "error")
            return redirect(url_for("auctions.item_detail", item_id=item_id))

        current_bid = get_current_bid(item)
        min_next = current_bid + item.bid_increment
        previous_leader = get_leading_bid(item_id, for_update=True)

        if amount < min_next:
            db.session.rollback()
            flash(f"Bid must be at least ${min_next:.2f}.", "error")
            return redirect(url_for("auctions.item_detail", item_id=item_id))

        db.session.add(
            Bid(
                item_id=item_id,
                bidder_id=current_user.id,
                amount=amount,
                is_auto=False,
            )
        )
        db.session.flush()

        resolve_autobids(item, last_bid_amount=amount, last_bidder_id=current_user.id)
        leading_bid = notify_bid_activity(item, previous_leader.bidder_id if previous_leader else None)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        flash("We could not record your bid right now. Please try again.", "error")
        return redirect(url_for("auctions.item_detail", item_id=item_id))

    if leading_bid and leading_bid.bidder_id == current_user.id:
        flash(f"Bid of ${amount:.2f} placed successfully. You are currently leading.", "success")
    else:
        flash(
            f"Bid of ${amount:.2f} was recorded, but the current highest bid is ${leading_bid.amount:.2f}.",
            "success",
        )

    return redirect(url_for("auctions.item_detail", item_id=item_id))


@auctions_bp.route("/<int:item_id>/autobid", methods=["POST"])
@login_required
def set_autobid(item_id):
    if not ensure_end_user():
        return redirect(url_for("auctions.item_detail", item_id=item_id))

    try:
        upper_limit = float(request.form.get("upper_limit", ""))
    except ValueError:
        flash("Invalid amount.", "error")
        return redirect(url_for("auctions.item_detail", item_id=item_id))

    try:
        item = get_locked_item_or_404(item_id)

        if item.status == "open" and item.close_time <= current_time():
            close_auction(item, commit=False)

        if item.status != "open":
            db.session.commit()
            flash("This auction is no longer open.", "error")
            return redirect(url_for("auctions.item_detail", item_id=item_id))

        if current_user.id == item.seller_id:
            db.session.rollback()
            flash("You cannot auto-bid on your own auction.", "error")
            return redirect(url_for("auctions.item_detail", item_id=item_id))

        current_bid = get_current_bid(item)
        min_next = current_bid + item.bid_increment
        previous_leader = get_leading_bid(item_id, for_update=True)
        is_current_leader = previous_leader is not None and previous_leader.bidder_id == current_user.id
        minimum_limit = current_bid if is_current_leader else min_next

        if upper_limit < minimum_limit:
            db.session.rollback()
            label = "current bid" if is_current_leader else "minimum next bid"
            flash(f"Auto-bid limit must be at least the {label} of ${minimum_limit:.2f}.", "error")
            return redirect(url_for("auctions.item_detail", item_id=item_id))

        AutoBid.query.filter_by(item_id=item_id, bidder_id=current_user.id).delete()
        db.session.add(AutoBid(item_id=item_id, bidder_id=current_user.id, upper_limit=upper_limit))

        leading_bid = previous_leader
        if not is_current_leader:
            db.session.add(
                Bid(
                    item_id=item_id,
                    bidder_id=current_user.id,
                    amount=min_next,
                    is_auto=True,
                )
            )
            db.session.flush()
            resolve_autobids(item, last_bid_amount=min_next, last_bidder_id=current_user.id)
            leading_bid = notify_bid_activity(item, previous_leader.bidder_id if previous_leader else None)

        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        flash("We could not save your auto-bid right now. Please try again.", "error")
        return redirect(url_for("auctions.item_detail", item_id=item_id))

    if leading_bid and leading_bid.bidder_id == current_user.id:
        flash(
            f"Auto-bid saved up to ${upper_limit:.2f}. You are currently leading at ${leading_bid.amount:.2f}.",
            "success",
        )
    else:
        flash(
            (
                f"Auto-bid saved up to ${upper_limit:.2f}. "
                f"The current highest bid is ${leading_bid.amount:.2f}, and the system will keep bidding for you "
                "until your limit is reached."
            ),
            "success",
        )

    return redirect(url_for("auctions.item_detail", item_id=item_id))


@auctions_bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    if not ensure_listing_seller():
        return redirect(url_for("search.browse"))

    categories = get_leaf_categories()
    selected_category = request.args.get("category_id", type=int)

    if request.method == "POST":
        close_time_raw = request.form.get("close_time", "")
        image_file = request.files.get("image_file")

        try:
            close_time = datetime.strptime(close_time_raw, "%Y-%m-%dT%H:%M")
            us_size = float(request.form.get("us_size", 0))
            category_id = int(request.form.get("category_id", 0))
            start_price = float(request.form.get("start_price", 0))
            reserve_price = float(request.form.get("reserve_price", 0) or 0)
            bid_increment = float(request.form.get("bid_increment", 1) or 1)
        except ValueError:
            flash("Please provide valid auction details.", "error")
            return render_create_form(categories, selected_category)

        title = request.form.get("title", "").strip()
        brand = request.form.get("brand", "").strip()
        model_name = request.form.get("model_name", "").strip()
        colorway = request.form.get("colorway", "").strip()
        style_code = request.form.get("style_code", "").strip()
        description = request.form.get("description", "").strip()

        if not all([title, brand, model_name, colorway, style_code, description]):
            flash("All listing fields are required.", "error")
            return render_create_form(categories, selected_category)

        if close_time <= current_time():
            flash("Closing time must be in the future.", "error")
            return render_create_form(categories, selected_category)

        if start_price <= 0 or reserve_price < 0 or bid_increment <= 0 or us_size <= 0:
            flash("Prices, bid increment, and size must be positive values.", "error")
            return render_create_form(categories, selected_category)

        selected_category_record = db.session.get(Category, category_id)
        if not selected_category_record:
            flash("Please choose a valid category.", "error")
            return render_create_form(categories, selected_category)
        if selected_category_record.subcategories:
            flash("Please choose a leaf sneaker category, not a parent branch.", "error")
            return render_create_form(categories, selected_category)

        stored_image_data = None
        if image_file and image_file.filename:
            stored_image_data, image_error = save_uploaded_item_image(image_file)
            if image_error:
                flash(image_error, "error")
                return render_create_form(categories, selected_category)

        item = Item(
            title=title,
            brand=brand,
            model_name=model_name,
            colorway=colorway,
            style_code=style_code,
            us_size=us_size,
            condition=request.form.get("condition", "new").strip().lower(),
            box_included="box_included" in request.form,
            description=description,
            seller_id=current_user.id,
            category_id=category_id,
            start_price=start_price,
            reserve_price=reserve_price,
            bid_increment=bid_increment,
            image_data=stored_image_data,
            close_time=close_time,
        )
        db.session.add(item)
        db.session.flush()

        for alert in Alert.query.options(selectinload(Alert.user)).filter_by(category_id=item.category_id).all():
            if alert.user_id == current_user.id:
                continue
            if item_matches_alert(item, alert):
                add_notification(
                    alert.user_id,
                    f"New item matching your alert: {item.title} in {item.category.name}.",
                )

        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            flash("We could not save this auction right now. Please try again.", "error")
            return render_create_form(categories, selected_category)

        flash("Auction listed successfully.", "success")
        return redirect(url_for("search.browse"))

    return render_create_form(categories, selected_category)


@auctions_bp.route("/<int:item_id>/question", methods=["POST"])
@login_required
def post_question(item_id):
    if not ensure_end_user():
        return redirect(url_for("auctions.item_detail", item_id=item_id))

    item = db.get_or_404(Item, item_id)
    body = request.form.get("body", "").strip()

    if body:
        db.session.add(Question(user_id=current_user.id, item_id=item_id, body=body))
        for staff_user in User.query.filter(User.role.in_(["rep", "admin"])).all():
            add_notification(staff_user.id, f"New question posted on {item.title}.")
        if item.seller_id != current_user.id:
            add_notification(item.seller_id, f"A buyer asked a new question on {item.title}.")
        db.session.commit()
        flash("Question posted.", "success")

    return redirect(url_for("auctions.item_detail", item_id=item_id))


@auctions_bp.route("/alerts", methods=["GET", "POST"])
@login_required
def alerts():
    if not ensure_end_user():
        return redirect(url_for("search.browse"))

    categories = get_leaf_categories()

    if request.method == "POST":
        category_id = request.form.get("category_id", type=int)
        keywords = request.form.get("keywords", "").strip()

        if not category_id:
            flash("Choose a category for your alert.", "error")
            return redirect(url_for("auctions.alerts"))

        category = db.session.get(Category, category_id)
        if category is None or category.subcategories:
            flash("Choose a leaf sneaker category for your alert.", "error")
            return redirect(url_for("auctions.alerts"))

        duplicate_alert = Alert.query.filter_by(
            user_id=current_user.id,
            category_id=category_id,
            keywords=keywords or None,
        ).first()
        if duplicate_alert:
            flash("That alert already exists.", "error")
            return redirect(url_for("auctions.alerts"))

        db.session.add(Alert(user_id=current_user.id, category_id=category_id, keywords=keywords or None))
        db.session.commit()
        flash("Alert saved. You will be notified when a matching pair is listed.", "success")
        return redirect(url_for("auctions.alerts"))

    saved_alerts = (
        Alert.query.options(selectinload(Alert.category))
        .filter_by(user_id=current_user.id)
        .order_by(Alert.id.desc())
        .all()
    )
    return render_template("auctions/alerts.html", categories=categories, saved_alerts=saved_alerts)


@auctions_bp.route("/alerts/<int:alert_id>/delete", methods=["POST"])
@login_required
def delete_alert(alert_id):
    alert = db.get_or_404(Alert, alert_id)
    if alert.user_id != current_user.id:
        flash("You can only remove your own alerts.", "error")
        return redirect(url_for("auctions.alerts"))

    db.session.delete(alert)
    db.session.commit()
    flash("Alert removed.", "success")
    return redirect(url_for("auctions.alerts"))


@auctions_bp.route("/notifications")
@login_required
def notifications():
    notifications_list = (
        Notification.query.filter_by(user_id=current_user.id)
        .order_by(Notification.is_read.asc(), Notification.created_at.desc(), Notification.id.desc())
        .all()
    )
    return render_template("auctions/notifications.html", notifications=notifications_list)


@auctions_bp.route("/notifications/mark-all-read", methods=["POST"])
@login_required
def mark_all_notifications_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    flash("All notifications marked as read.", "success")
    return redirect(url_for("auctions.notifications"))


@auctions_bp.route("/notifications/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_notification_read(notification_id):
    notification = db.get_or_404(Notification, notification_id)
    if notification.user_id != current_user.id:
        flash("You can only update your own notifications.", "error")
        return redirect(url_for("auctions.notifications"))

    notification.is_read = True
    db.session.commit()
    flash("Notification marked as read.", "success")
    return redirect(url_for("auctions.notifications"))
