from flask import Flask, request, jsonify, redirect
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import string
import random
import re
from urllib.parse import urlparse
import os
from google.cloud.sql.connector import Connector
import sqlalchemy

BASE_URL = os.getenv('BASE_URL', 'http://localhost:5001')

app = Flask(__name__)
CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:5173"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

def init_connection_pool():
    if os.getenv('ENVIRONMENT') == 'production':
        connector = Connector()
        def getconn():
            conn = connector.connect(
                os.getenv('CLOUD_SQL_CONNECTION_NAME'),
                'pg8000',
                user=os.getenv('DB_USER'),
                password=os.getenv('DB_PASS'),
                db=os.getenv('DB_NAME')
            )
            return conn

        engine = sqlalchemy.create_engine(
            "postgresql+pg8000://",
            creator=getconn,
        )
        return engine
    else:
        return 'sqlite:///urls.db'

if os.getenv('ENVIRONMENT') == 'production':
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': 5,
        'pool_timeout': 30,
        'pool_recycle': -1,
        'max_overflow': 2,
        'pool_pre_ping': True,
        'pool_reset_on_return': None,
    }
    app.config['SQLALCHEMY_DATABASE_URI'] = init_connection_pool()
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///urls.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


class URL(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_url = db.Column(db.String(2048), nullable=False)
    short_code = db.Column(db.String(10), unique=True, nullable=False)
    clicks = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())


def generate_short_code(length=6):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))


def is_valid_url(url):
    pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return pattern.match(url) is not None


@app.route('/api/shorten', methods=['POST'])
def shorten_url():
    data = request.get_json()
    original_url = data.get('url')

    if not original_url:
        return jsonify({'error': 'URL is required'}), 400

    if not is_valid_url(original_url):
        return jsonify({'error': 'Invalid URL format'}), 400

    # Check if URL already exists
    existing = URL.query.filter_by(original_url=original_url).first()
    if existing:
        return jsonify({
            'short_url': f'{BASE_URL}/{existing.short_code}',
            'short_code': existing.short_code
        })

    # Generate unique short code
    while True:
        short_code = generate_short_code()
        if not URL.query.filter_by(short_code=short_code).first():
            break

    new_url = URL(original_url=original_url, short_code=short_code)
    db.session.add(new_url)
    db.session.commit()

    return jsonify({
        'short_url': f'{BASE_URL}/{short_code}',
        'short_code': short_code
    })


@app.route('/<short_code>')
def redirect_url(short_code):
    url = URL.query.filter_by(short_code=short_code).first()
    if not url:
        return jsonify({'error': 'URL not found'}), 404

    # Increment click counter
    url.clicks += 1
    db.session.commit()

    return redirect(url.original_url)


@app.route('/api/stats/<short_code>')
def get_stats(short_code):
    url = URL.query.filter_by(short_code=short_code).first()
    if not url:
        return jsonify({'error': 'URL not found'}), 404

    return jsonify({
        'short_code': url.short_code,
        'original_url': url.original_url,
        'clicks': url.clicks,
        'created_at': url.created_at.isoformat()
    })


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5001)