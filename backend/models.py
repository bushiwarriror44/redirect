from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class RedirectLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), nullable=False, unique=True, index=True)
    target_url = db.Column(db.Text, nullable=False)
    click_count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


def init_all_models():
    db.create_all()
