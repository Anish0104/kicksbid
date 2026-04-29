# KicksBid DB Snapshot

## Tables

- `alerts`
- `answers`
- `autobids`
- `bids`
- `categories`
- `items`
- `notifications`
- `questions`
- `users`

## Views

- `active_auction_summary`
- `closed_auction_sales`
- `rep_moderation_queue`
- `user_auction_participation`

## Functions

- `fn_get_current_bid`

## Stored Procedures

- `sp_recalculate_item_status`
- `sp_close_all_expired_auctions`
- `sp_process_autobids`

## Triggers

- `trg_bids_before_insert_validate`
- `trg_autobids_before_insert_validate`

## Events

- `evt_close_expired_auctions`

## Notes

- ORM schema source is `models.py`.
- Physical DB is MySQL database `kicksbid` on localhost.
- Advanced DB artifacts are installed by `python seed.py` through `db_artifacts.py`.
- Row counts depend on the current live database contents.
