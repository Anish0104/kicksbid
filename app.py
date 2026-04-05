import os

from flask import Flask, redirect, url_for
from extensions import db, login_manager

app = Flask(__name__)

app.config["SECRET_KEY"] = "kicksbid-secret-2024"
app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+pymysql://root:anish08032003@localhost/kicksbid"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = "auth.login"


@login_manager.user_loader
def load_user(user_id):
    from models import User

    return db.session.get(User, int(user_id))


with app.app_context():
    from models import User, Category, Item, Bid, AutoBid, Alert, Question, Answer, Notification

    db.create_all()


@app.route("/")
def index():
    return redirect(url_for("search.browse"))


from routes.auth import auth_bp
from routes.auctions import auctions_bp
from routes.search import search_bp
from routes.admin import admin_bp

app.register_blueprint(auth_bp)
app.register_blueprint(auctions_bp)
app.register_blueprint(search_bp)
app.register_blueprint(admin_bp)


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5001"))
    debug = os.getenv("FLASK_DEBUG", "1") == "1"
    app.run(host=host, port=port, debug=debug)
