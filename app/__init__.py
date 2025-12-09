from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from pathlib import Path
import os

# Extensiones globales

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access this page."  # mensaje visible
login_manager.login_message_category = "info"


def create_app() -> Flask:
	app = Flask(__name__, template_folder="../templates", static_folder="../static")
	# Configuración básica
	app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")
	db_path = os.environ.get("DATABASE_URL")
	if not db_path:
		base_dir = Path(app.root_path).parent
		db_path = f"sqlite:///{base_dir / 'data.db'}"
	app.config["SQLALCHEMY_DATABASE_URI"] = db_path
	app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

	db.init_app(app)
	login_manager.init_app(app)

	# Blueprints
	from .routes import main_bp, auth_bp, data_bp
	app.register_blueprint(auth_bp)
	app.register_blueprint(main_bp)
	app.register_blueprint(data_bp)

	with app.app_context():
		from . import models  # asegura el registro de modelos
		db.create_all()

	return app
