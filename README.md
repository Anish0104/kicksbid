# KicksBid

KicksBid is a full-stack sneaker auction marketplace built with Flask and MySQL. It supports live auctions, automatic bidding, buyer alerts, role-based moderation, and a rich set of database-level business logic — including triggers, stored procedures, views, and an event scheduler.

## Overview

- User accounts with registration, login, account management, and role-based permissions (buyer, seller, rep, admin)
- Auction listings with reserve prices, configurable bid increments, manual bidding, and auto-bidding
- Buyer notifications for outbid events, alert matches, and auction outcomes
- Search and browse flows with sneaker-specific filters (brand, size, condition, category, price, status)
- Rep and admin workflows for moderation, reporting, Q&A management, and buyer/seller analytics
- MySQL views, triggers, functions, procedures, and an event scheduler for auction automation

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Flask, Flask-Login, Flask-SQLAlchemy |
| Database | MySQL |
| ORM | SQLAlchemy |
| Driver | PyMySQL |
| Image handling | Pillow |

## Quick Start

### 1. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Create the MySQL database

Start MySQL locally, then create the database:

```bash
mysql -u root -p
```

Inside the MySQL prompt:

```sql
CREATE DATABASE kicksbid;
EXIT;
```

### 4. Configure the database connection

The app reads the database connection from `DATABASE_URL`. If not set, `app.py` falls back to:

```
mysql+pymysql://root:anish08032003@localhost/kicksbid
```

If your local MySQL credentials differ, export your own connection string:

```bash
export DATABASE_URL="mysql+pymysql://root:yourpassword@localhost/kicksbid"
```

### 5. Initialize schema, data, and database artifacts

The app creates tables automatically on startup. To initialize the required three-level sneaker category tree, create the admin account, normalize legacy condition values, and install the MySQL indexes/views/functions/procedures/triggers/event, run:

```bash
python seed.py
```

If you previously ran an older one-level category version of the project, rerunning `seed.py` also migrates those legacy categories into the deeper hierarchy.

Default admin credentials created by `seed.py`:

```
username: admin
email:    admin@kicksbid.local
password: admin12345
```

Override them at setup time if needed:

```bash
python seed.py --admin-username youradmin --admin-email you@example.com --admin-password yourpassword
```

If you previously loaded an older demo dataset, remove it first:

```bash
python scripts/purge_demo_data.py
```

### 6. Start the app

```bash
python app.py
```

The development server listens on port `5001` by default:

```
http://127.0.0.1:5001
```

Override runtime settings as needed:

```bash
HOST=127.0.0.1 PORT=5001 FLASK_DEBUG=1 python app.py
```

## Database Diagram

![KicksBid ER Diagram](ERRDiagram.png)

## Database Documentation

| File | Contents |
|---|---|
| `docs/ERD.md` | Canonical Mermaid source for the schema diagram |
| `docs/kicksbid-er-diagram.png` | Generated diagram export |
| `docs/kicksbid-er-diagram.mmd` | Mermaid diagram source |
| `docs/DB_FEATURES.md` | Full reference for views, triggers, procedures, and DB-layer features |
| `schema.sql` | Canonical MySQL schema |

Regenerate diagram assets locally:

```bash
python3 scripts/generate_er_diagram.py
```

## Feature Highlights

### Auction and bidding

- Create listings with category assignment, reserve prices, and sneaker metadata
- Place manual bids or configure a maximum auto-bid that competes incrementally
- Auctions resolve automatically into sold, closed, or no-winner outcomes via the event scheduler
- View item detail pages with full bid history and historical pricing context

### Discovery and alerts

- Browse by keyword, category, seller, brand, size, condition, price, and auction status
- Save alerts for future listings in tracked categories
- Ask public questions on listings and receive rep answers
- Receive in-app notifications for bidding events and listing activity

### Staff and reporting

- Promote users to rep roles and manage staff permissions from the admin dashboard
- Moderate auctions, users, bids, and Q&A entries
- Review sales reports, buyer rankings, and per-seller, per-category, and per-item earnings

## Database Systems Features

- Self-referential category hierarchy supporting a three-level sneaker taxonomy (brand → line → model)
- Explicit foreign-key behavior with `ON DELETE RESTRICT` and `ON UPDATE CASCADE`
- Check constraint `ck_items_condition` plus bid and auto-bid trigger validation
- Summary views: `active_auction_summary`, `closed_auction_sales`, `user_auction_participation`, `rep_moderation_queue`
- Reusable scalar function `fn_get_current_bid(item_id)` for current-bid calculation across the app
- Stored procedures for auction status recalculation, expired-auction closure, and auto-bid processing via `sp_process_autobids`
- Event scheduler job `evt_close_expired_auctions` for automated auction lifecycle management
- Seed-driven installation and repair of all DB artifacts through `db_artifacts.py`

## Team Contributions

### Anish Shirodkar
- Designed and implemented the core auction engine — auction creation, manual bidding, auto-bidding logic, bid increment enforcement, and auction resolution workflows (`routes/auctions.py`)
- Authored the MySQL schema (`schema.sql`) and all database-layer artifacts: triggers for bid/auto-bid validation, stored procedures for auto-bid processing and auction lifecycle management, summary views, and the `fn_get_current_bid` scalar function (`db_artifacts.py`)
- Built the app infrastructure: Flask application factory, blueprint registration, startup initialization, and environment-based configuration (`app.py`, `extensions.py`)
- Produced the ER diagram, database documentation, and canonical schema exports (`docs/`)

### Dwiti Choksi
- Built the admin dashboard and moderation system — user management, auction moderation, bid removal, and Q&A oversight (`routes/admin.py`)
- Implemented the rep role system: rep promotion, rep moderation queue, and rep-specific workflows
- Developed the reporting layer: sales summaries, buyer rankings, and per-seller, per-category, and per-item earnings views (`templates/admin/`)

### Charvi Shastri
- Defined all SQLAlchemy models and table relationships, including the self-referential category hierarchy and all association logic (`models.py`)
- Built the search and browse system — keyword search, multi-filter browsing by brand, size, condition, price, and status, and the activity feed (`routes/search.py`)
- Developed Q&A functionality: public question submission, rep answer flow, and the questions listing page (`templates/search/`)
- Implemented image upload handling and processing utilities (`image_utils.py`)

### Sinchana Arun
- Implemented user authentication — registration, login/logout, session management, and account settings (`routes/auth.py`, `templates/auth/`)
- Built the notifications and alerts system: outbid notifications, alert creation for tracked categories, and the alerts management page (`templates/auctions/`)
- Wrote the seed script and demo data pipeline: category tree bootstrap, admin account setup, and sample inventory/bid loading (`seed.py`, `scripts/`)
- Contributed timezone-aware datetime utilities used across the auction and notification flows (`time_utils.py`)

## Project Structure

```
kicksbid/
├── app.py                        # Flask app setup, config, startup, route registration
├── models.py                     # SQLAlchemy models and relationships
├── db_artifacts.py               # MySQL views, triggers, procedures, event installer
├── seed.py                       # Category bootstrap, admin setup, sample data
├── schema.sql                    # Canonical SQL schema
├── extensions.py                 # Shared Flask extensions (db, login manager)
├── image_utils.py                # Image upload and processing helpers
├── time_utils.py                 # Timezone and datetime utilities
├── routes/
│   ├── auth.py                   # Registration, login, account management
│   ├── auctions.py               # Listings, bidding, auto-bids, notifications
│   ├── search.py                 # Search, browse, alerts, Q&A
│   └── admin.py                  # Admin dashboard, rep tools, moderation, reports
├── templates/                    # Jinja2 HTML templates
├── static/                       # Favicons, sneaker cutout images
├── scripts/
│   ├── generate_er_diagram.py    # ER diagram export generator
│   ├── load_demo_data.py         # Sample data loader
│   └── purge_demo_data.py        # Cleanup script for demo data
└── docs/                         # ERD and database documentation
```
