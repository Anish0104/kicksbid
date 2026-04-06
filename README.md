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

This project currently connects to MySQL with the database URL hard-coded in `app.py`:

```python
mysql+pymysql://root:anish08032003@localhost/kicksbid
```

If your local MySQL username or password is different, update that value in `app.py` before starting the app.

### 4. Optional: load sample data

The app will create tables automatically on startup. If you want demo users, categories, and auction listings, run:

```bash
python seed.py
```

Sample accounts created by `seed.py`:

- User: `alice@test.com` / `password`
- User: `bob@test.com` / `password`
- Rep: `sarah@kicksbid.com` / `rep`
- Admin: `admin@kicksbid.com` / `admin123`

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

## Project files

- `app.py`: Flask app setup and route registration
- `models.py`: SQLAlchemy models
- `routes/`: auth, auctions, admin, and search routes
- `templates/`: Jinja templates for the UI
- `seed.py`: sample data loader
- `schema.sql`: exported MySQL schema snapshot
