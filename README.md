# KicksBid

KicksBid is a Flask + MySQL sneaker marketplace and auction app.

## Run locally

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

```sql
CREATE DATABASE kicksbid;
```

Run that SQL inside the MySQL client, not your normal terminal shell. For example:

```bash
mysql -u root -p
```

Then inside the MySQL prompt:

```sql
CREATE DATABASE kicksbid;
EXIT;
```

This project reads the database URL from `DATABASE_URL` and falls back to this local MySQL default in `app.py`:

```python
mysql+pymysql://root:anish08032003@localhost/kicksbid
```

If your local MySQL username or password is different, export `DATABASE_URL` before starting the app. Example:

```bash
export DATABASE_URL="mysql+pymysql://root:yourpassword@localhost/kicksbid"
```

### 4. Initialize required catalog data

The app creates tables automatically on startup. To initialize the required sneaker category tree, run:

```bash
python seed.py
```

If you also want to create or update the admin account during setup, pass real credentials:

```bash
python seed.py --admin-username youradmin --admin-email you@example.com --admin-password yourpassword
```

If you previously loaded the old demo dataset, remove it with:

```bash
python scripts/purge_demo_data.py
```

### 5. Start the app

```bash
python app.py
```

By default the server runs at:

```text
http://127.0.0.1:5001
```

You can override the host, port, or debug mode if needed:

```bash
HOST=127.0.0.1 PORT=5001 FLASK_DEBUG=1 python app.py
```

## Database ER diagram

The generated diagram assets live at:

- `docs/kicksbid-er-diagram.png`
- `docs/kicksbid-er-diagram.pdf`
- `docs/kicksbid-er-diagram.mmd`
- `docs/ERD.md`

For the cleanest source-of-truth version on GitHub, open `docs/ERD.md`.

To regenerate it locally:

```bash
python3 scripts/generate_er_diagram.py
```

![KicksBid ER Diagram](docs/kicksbid-er-diagram.png)

## Implemented project features

- End-user accounts: register, login, logout, and self-delete/deactivate
- Auctions: create listings, reserve price, bid increment, manual bidding, automatic bidding, winner/no-winner resolution
- Notifications: outbid alerts, auto-bid limit alerts, winner alerts, seller sale alerts, and saved item alerts
- Search and browse: keyword, category, condition, price, brand, size, seller, box-included, and status filters
- History views: bid history per auction plus buyer/seller participation history
- Similar items: historical similar auctions from the previous month on each item page
- Q&A: item questions, rep answers, public Q&A browse/search page
- Admin tools: create rep accounts, promote users to reps, sales reporting, buyer rankings, seller/category/item earnings
- Rep tools: answer questions, edit users, edit auctions, remove bids, and remove auctions

## Team

- Repository contributor detected from git history: `Anish0104`
- Add any additional teammate names here before final submission if they are not yet reflected in git history.

## Project files

- `app.py`: Flask app setup and route registration
- `models.py`: SQLAlchemy models
- `routes/`: auth, auctions, admin, and search routes
- `templates/`: Jinja templates for the UI
- `seed.py`: core catalog/admin bootstrap script
- `scripts/purge_demo_data.py`: removes the old demo/sample records from an existing database
- `schema.sql`: exported MySQL schema snapshot
