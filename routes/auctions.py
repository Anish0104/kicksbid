from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db
from models import Alert, AutoBid, Bid, Category, Item, Notification, Question

auctions_bp = Blueprint("auctions", __name__, url_prefix="/auctions")


def get_current_bid(item):
    bids = Bid.query.filter_by(item_id=item.id).all()
    return max((bid.amount for bid in bids), default=item.start_price)


def close_auction(item):
    bids = Bid.query.filter_by(item_id=item.id).order_by(Bid.amount.desc(), Bid.placed_at.asc()).all()
    top_bid = bids[0] if bids else None

    if not top_bid or top_bid.amount < item.reserve_price:
        item.status = "no_winner"
    else:
        item.status = "closed"
        db.session.add(
            Notification(
                user_id=top_bid.bidder_id,
                message=f"Congratulations! You won {item.title} with a bid of ${top_bid.amount:.2f}.",
            )
        )

    db.session.commit()


def maybe_close_item(item):
    if item.status == "open" and item.close_time <= datetime.utcnow():
        close_auction(item)


def run_autobid(item_id, new_amount, triggered_by_id):
    item = db.session.get(Item, item_id)
    if item is None or item.status != "open":
        return

    autobids = AutoBid.query.filter_by(item_id=item_id).order_by(AutoBid.upper_limit.desc()).all()
    for autobid in autobids:
        if autobid.bidder_id == triggered_by_id:
            continue
        if autobid.upper_limit > new_amount:
            next_amount = min(new_amount + item.bid_increment, autobid.upper_limit)
            db.session.add(
                Bid(
                    item_id=item_id,
                    bidder_id=autobid.bidder_id,
                    amount=next_amount,
                    is_auto=True,
                )
            )
            db.session.add(
                Notification(
                    user_id=triggered_by_id,
                    message=f"You have been outbid on {item.title}. New bid: ${next_amount:.2f}.",
                )
            )
            db.session.commit()
            run_autobid(item_id, next_amount, autobid.bidder_id)
            return


@auctions_bp.route("/<int:item_id>")
def item_detail(item_id):
    item = db.get_or_404(Item, item_id)
    maybe_close_item(item)
    bids = Bid.query.filter_by(item_id=item_id).order_by(Bid.amount.desc(), Bid.placed_at.desc()).all()
    questions = Question.query.filter_by(item_id=item_id).order_by(Question.created_at.desc()).all()
    current_bid = get_current_bid(item)
    return render_template(
        "auctions/item_detail.html",
        item=item,
        bids=bids,
        current_bid=current_bid,
        questions=questions,
    )


@auctions_bp.route("/<int:item_id>/bid", methods=["POST"])
@login_required
def place_bid(item_id):
    item = db.get_or_404(Item, item_id)
    maybe_close_item(item)

    if item.status != "open":
        flash("This auction is no longer open.", "error")
        return redirect(url_for("auctions.item_detail", item_id=item_id))

    if current_user.id == item.seller_id:
        flash("You cannot bid on your own auction.", "error")
        return redirect(url_for("auctions.item_detail", item_id=item_id))

    current_bid = get_current_bid(item)
    min_next = current_bid + item.bid_increment

    try:
        amount = float(request.form.get("amount", ""))
    except ValueError:
        flash("Invalid bid amount.", "error")
        return redirect(url_for("auctions.item_detail", item_id=item_id))

    if amount < min_next:
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
    db.session.commit()
    run_autobid(item_id, amount, current_user.id)
    flash(f"Bid of ${amount:.2f} placed successfully.", "success")
    return redirect(url_for("auctions.item_detail", item_id=item_id))


@auctions_bp.route("/<int:item_id>/autobid", methods=["POST"])
@login_required
def set_autobid(item_id):
    item = db.get_or_404(Item, item_id)
    maybe_close_item(item)

    if item.status != "open":
        flash("This auction is no longer open.", "error")
        return redirect(url_for("auctions.item_detail", item_id=item_id))

    current_bid = get_current_bid(item)
    min_next = current_bid + item.bid_increment

    try:
        upper_limit = float(request.form.get("upper_limit", ""))
    except ValueError:
        flash("Invalid amount.", "error")
        return redirect(url_for("auctions.item_detail", item_id=item_id))

    if upper_limit < min_next:
        flash(f"Auto-bid limit must be at least ${min_next:.2f}.", "error")
        return redirect(url_for("auctions.item_detail", item_id=item_id))

    AutoBid.query.filter_by(item_id=item_id, bidder_id=current_user.id).delete()
    db.session.add(
        AutoBid(
            item_id=item_id,
            bidder_id=current_user.id,
            upper_limit=upper_limit,
        )
    )
    db.session.add(
        Bid(
            item_id=item_id,
            bidder_id=current_user.id,
            amount=min_next,
            is_auto=True,
        )
    )
    db.session.commit()
    run_autobid(item_id, min_next, current_user.id)
    flash(f"Auto-bid set up to ${upper_limit:.2f}.", "success")
    return redirect(url_for("auctions.item_detail", item_id=item_id))


@auctions_bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    categories = Category.query.filter(Category.parent_id.isnot(None)).order_by(Category.name.asc()).all()

    if request.method == "POST":
        close_time_raw = request.form.get("close_time", "")
        close_time = datetime.strptime(close_time_raw, "%Y-%m-%dT%H:%M")

        item = Item(
            title=request.form.get("title", "").strip(),
            brand=request.form.get("brand", "").strip(),
            model_name=request.form.get("model_name", "").strip(),
            colorway=request.form.get("colorway", "").strip(),
            style_code=request.form.get("style_code", "").strip(),
            us_size=float(request.form.get("us_size", 0)),
            condition=request.form.get("condition", "DS"),
            box_included="box_included" in request.form,
            description=request.form.get("description", "").strip(),
            seller_id=current_user.id,
            category_id=int(request.form.get("category_id", 0)),
            start_price=float(request.form.get("start_price", 0)),
            reserve_price=float(request.form.get("reserve_price", 0) or 0),
            bid_increment=float(request.form.get("bid_increment", 1) or 1),
            close_time=close_time,
        )
        db.session.add(item)
        db.session.commit()

        alerts = Alert.query.filter_by(category_id=item.category_id).all()
        for alert in alerts:
            if alert.user_id == current_user.id:
                continue
            keywords = (alert.keywords or "").strip().lower()
            if not keywords or keywords in item.title.lower() or keywords in item.brand.lower():
                db.session.add(
                    Notification(
                        user_id=alert.user_id,
                        message=f"New item matching your alert: {item.title}",
                    )
                )
        db.session.commit()

        flash("Auction listed successfully.", "success")
        return redirect(url_for("search.browse"))

    return render_template("auctions/create.html", categories=categories)


@auctions_bp.route("/<int:item_id>/question", methods=["POST"])
@login_required
def post_question(item_id):
    body = request.form.get("body", "").strip()
    if body:
        db.session.add(Question(user_id=current_user.id, item_id=item_id, body=body))
        db.session.commit()
        flash("Question posted.", "success")
    return redirect(url_for("auctions.item_detail", item_id=item_id))
