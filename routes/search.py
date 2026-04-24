from datetime import datetime

from flask import Blueprint, render_template, request
from flask_login import current_user
from sqlalchemy import or_
from sqlalchemy.orm import selectinload

from models import Answer, Bid, Category, Item, Question, User

search_bp = Blueprint("search", __name__, url_prefix="/search")


def get_current_bid(item):
    bids = Bid.query.filter_by(item_id=item.id).all()
    return max((bid.amount for bid in bids), default=item.start_price)


@search_bp.route("/browse")
def browse():
    now = datetime.utcnow()
    query = Item.query.options(selectinload(Item.seller), selectinload(Item.category))

    q = request.args.get("q", "").strip()
    category_id = request.args.get("category_id", type=int)
    condition = request.args.get("condition", "")
    min_price = request.args.get("min_price", type=float)
    max_price = request.args.get("max_price", type=float)
    seller_id = request.args.get("seller_id", type=int)
    brand = request.args.get("brand", "").strip()
    us_size = request.args.get("us_size", type=float)
    box_included = request.args.get("box_included", "")
    status = request.args.get("status", "open")
    sort = request.args.get("sort", "ending")

    if status == "open":
        query = query.filter(Item.status == "open", Item.close_time > now)
    elif status != "all":
        query = query.filter(Item.status == status)

    if q:
        query = query.filter(
            or_(
                Item.title.ilike(f"%{q}%"),
                Item.brand.ilike(f"%{q}%"),
                Item.colorway.ilike(f"%{q}%"),
                Item.model_name.ilike(f"%{q}%"),
                Item.description.ilike(f"%{q}%"),
                Item.style_code.ilike(f"%{q}%"),
            )
        )

    if category_id:
        query = query.filter_by(category_id=category_id)

    if condition:
        query = query.filter_by(condition=condition)

    if seller_id:
        query = query.filter_by(seller_id=seller_id)

    if brand:
        query = query.filter(Item.brand.ilike(f"%{brand}%"))

    if us_size is not None:
        query = query.filter(Item.us_size == us_size)

    if box_included == "yes":
        query = query.filter(Item.box_included.is_(True))
    elif box_included == "no":
        query = query.filter(Item.box_included.is_(False))

    if sort == "ending":
        query = query.order_by(Item.close_time.asc())
    elif sort == "newest":
        query = query.order_by(Item.created_at.desc())
    elif sort == "recently_closed":
        query = query.order_by(Item.close_time.desc())

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
    sellers = User.query.filter_by(role="user").order_by(User.username.asc()).all()
    current_bids = {item.id: get_current_bid(item) for item in items}

    return render_template(
        "search/browse.html",
        items=items,
        categories=categories,
        sellers=sellers,
        current_bids=current_bids,
        now=now,
        q=q,
        selected_category=category_id,
        selected_condition=condition,
        selected_seller=seller_id,
        selected_brand=brand,
        selected_status=status,
        selected_box_included=box_included,
        selected_us_size=us_size,
        sort=sort,
        min_price=min_price,
        max_price=max_price,
    )


@search_bp.route("/questions")
def questions():
    q = request.args.get("q", "").strip()
    answered = request.args.get("answered", "")

    query = Question.query.options(
        selectinload(Question.item),
        selectinload(Question.user),
        selectinload(Question.answers).selectinload(Answer.rep),
    )

    if q:
        query = (
            query.outerjoin(Answer)
            .join(Item)
            .filter(
                or_(
                    Question.body.ilike(f"%{q}%"),
                    Answer.body.ilike(f"%{q}%"),
                    Item.title.ilike(f"%{q}%"),
                )
            )
            .distinct()
        )

    if answered == "yes":
        query = query.filter(Question.answers.any())
    elif answered == "no":
        query = query.filter(~Question.answers.any())

    question_rows = query.order_by(Question.created_at.desc()).all()
    return render_template(
        "search/questions.html",
        questions=question_rows,
        q=q,
        answered=answered,
    )


@search_bp.route("/activity")
def activity():
    seller_id = request.args.get("seller_id", type=int)
    bidder_id = request.args.get("bidder_id", type=int)

    if not seller_id and not bidder_id and current_user.is_authenticated and current_user.role == "user":
        seller_id = current_user.id
        bidder_id = current_user.id

    users = User.query.filter(User.role.in_(["user", "deleted"])).order_by(User.username.asc()).all()
    selected_seller = User.query.filter_by(id=seller_id).first() if seller_id else None
    selected_bidder = User.query.filter_by(id=bidder_id).first() if bidder_id else None

    seller_auctions = []
    bidder_auctions = []
    bidder_max_bids = {}

    if seller_id:
        seller_auctions = (
            Item.query.options(selectinload(Item.category), selectinload(Item.bids))
            .filter_by(seller_id=seller_id)
            .order_by(Item.close_time.desc(), Item.created_at.desc())
            .all()
        )

    if bidder_id:
        bidder_auctions = (
            Item.query.options(selectinload(Item.seller), selectinload(Item.category), selectinload(Item.bids))
            .join(Bid)
            .filter(Bid.bidder_id == bidder_id)
            .distinct()
            .order_by(Item.close_time.desc(), Item.created_at.desc())
            .all()
        )
        bidder_max_bids = {
            item.id: max((bid.amount for bid in item.bids if bid.bidder_id == bidder_id), default=None)
            for item in bidder_auctions
        }

    seller_ids = {row.id for row in seller_auctions}
    combined_items = seller_auctions + [item for item in bidder_auctions if item.id not in seller_ids]
    current_bids = {item.id: get_current_bid(item) for item in combined_items}

    return render_template(
        "search/activity.html",
        users=users,
        selected_seller=selected_seller,
        selected_bidder=selected_bidder,
        seller_auctions=seller_auctions,
        bidder_auctions=bidder_auctions,
        bidder_max_bids=bidder_max_bids,
        current_bids=current_bids,
    )
