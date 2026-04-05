from datetime import datetime

from flask import Blueprint, render_template, request

from models import Bid, Category, Item

search_bp = Blueprint("search", __name__, url_prefix="/search")


def get_current_bid(item):
    bids = Bid.query.filter_by(item_id=item.id).all()
    return max((bid.amount for bid in bids), default=item.start_price)


@search_bp.route("/browse")
def browse():
    query = Item.query.filter_by(status="open")
    q = request.args.get("q", "").strip()
    category_id = request.args.get("category_id", type=int)
    condition = request.args.get("condition", "")
    min_price = request.args.get("min_price", type=float)
    max_price = request.args.get("max_price", type=float)
    sort = request.args.get("sort", "ending")

    if q:
        query = query.filter(
            Item.title.ilike(f"%{q}%")
            | Item.brand.ilike(f"%{q}%")
            | Item.colorway.ilike(f"%{q}%")
            | Item.model_name.ilike(f"%{q}%")
        )

    if category_id:
        query = query.filter_by(category_id=category_id)

    if condition:
        query = query.filter_by(condition=condition)

    if sort == "ending":
        query = query.order_by(Item.close_time.asc())
    elif sort == "newest":
        query = query.order_by(Item.created_at.desc())

    items = query.all()
    if min_price is not None:
        items = [item for item in items if get_current_bid(item) >= min_price]
    if max_price is not None:
        items = [item for item in items if get_current_bid(item) <= max_price]

    if sort == "price_low":
        items = sorted(items, key=get_current_bid)
    elif sort == "price_high":
        items = sorted(items, key=get_current_bid, reverse=True)

    categories = Category.query.filter(Category.parent_id.isnot(None)).order_by(Category.name.asc()).all()
    current_bids = {item.id: get_current_bid(item) for item in items}

    return render_template(
        "search/browse.html",
        items=items,
        categories=categories,
        current_bids=current_bids,
        now=datetime.utcnow(),
        q=q,
        selected_category=category_id,
        selected_condition=condition,
        sort=sort,
        min_price=min_price,
        max_price=max_price,
    )
