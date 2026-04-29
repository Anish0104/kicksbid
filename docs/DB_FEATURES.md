# KicksBid Database Features

This project now includes database-level artifacts beyond the ORM tables so the MySQL layer carries part of the application logic expected in a database systems project.

## Indexes

- Auction lookup indexes on `items(status, close_time)` and `items(category_id, status, close_time)` speed up live-auction browse queries.
- Bid history indexes on `bids(item_id, amount, placed_at, id)` and `bids(bidder_id, placed_at)` support winner resolution and buyer activity lookups.
- Notification, Q&A, and moderation paths use supporting indexes on `notifications`, `questions`, and `answers`.
- `autobids(item_id, bidder_id)` is unique so each user has at most one saved auto-bid per auction.
- A full-text index on key item description columns documents the intended database search path for future SQL-native search optimization.

## Views

- `active_auction_summary` exposes updatable open-auction rows and uses `WITH CHECK OPTION` so writes through the view must still satisfy `status = 'open'`.
- `closed_auction_sales` exposes the winning buyer and final sale price for completed auctions.
- `user_auction_participation` summarizes each user's listing, bidding, and winning activity.
- `rep_moderation_queue` gives staff a join-ready view of questions, askers, items, and any existing answer.

## Functions

- `fn_get_current_bid(item_id)` returns the current effective bid for an auction, falling back to `start_price` when no bids exist, and complements the updatable `active_auction_summary` view.

## Stored Procedures

- `sp_recalculate_item_status(item_id)` recomputes whether an auction should be `open`, `closed`, or `no_winner`, and now wraps the status update in an explicit transaction with an error handler.
- `sp_close_all_expired_auctions()` iterates over expired open auctions and applies the recalculation procedure.
- `sp_process_autobids(item_id, last_bid_amount, last_bidder_id)` performs the auto-bid counter-bid cascade inside MySQL.

## Triggers

- `trg_bids_before_insert_validate` prevents seller self-bids, expired-auction bids, and below-increment bids.
- `trg_autobids_before_insert_validate` prevents invalid auto-bid limits and seller self-auto-bids.
- The project uses `sp_process_autobids` for the auto-bid cascade instead of a same-table `AFTER INSERT` trigger because MySQL can reject triggers that insert back into the table that fired them.

## Event Scheduler

- `evt_close_expired_auctions` runs every minute and calls `sp_close_all_expired_auctions()`.
- `seed.py` attempts to enable `event_scheduler` globally and prints a warning instead of crashing if the local MySQL user lacks the required privilege.

## Foreign-Key Rules

- `ck_items_condition` restricts sneaker condition values to `new`, `used`, `like_new`, `good`, or `fair` at the database level.
- Auction-facing foreign keys now declare `ON DELETE RESTRICT ON UPDATE CASCADE` explicitly, so parent rows cannot disappear while dependent auction data exists, but key updates propagate consistently.
- `seed.py` installs these rules through `db_artifacts.py`, so a local schema can be repaired to the canonical constraint definitions without hand-editing MySQL tables.

## Installation

- Run `python seed.py` after creating the MySQL database.
- The seed script initializes the category hierarchy, normalizes legacy condition values, creates the admin account, and installs the database artifacts from `db_artifacts.py`.
