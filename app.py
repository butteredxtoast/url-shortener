from flask import Flask, request, jsonify, redirect
from flask_sqlalchemy import SQLAlchemy
import string
import random
import re
import os
from google.cloud.sql.connector import Connector
import sqlalchemy
from google.cloud import bigquery
from datetime import datetime

def get_base_url():
    # Check if we have forwarded headers (production with reverse proxy)
    if request.headers.get('X-Forwarded-Proto') and request.headers.get('Host'):
        proto = request.headers.get('X-Forwarded-Proto')
        host = request.headers.get('Host')
        return f"{proto}://{host}"

    # Fallback to request.url_root for development
    return request.url_root.rstrip('/')

app = Flask(__name__)


@app.after_request
def after_request(response):
    origin = request.headers.get('Origin')
    allowed_origins = [
        'https://url-shortener-464622.web.app',
        'http://localhost:5173'
    ]

    if origin in allowed_origins:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'

    return response


def get_connection_creator():
    """Returns a connection creator function for production database"""
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

    return getconn


if os.getenv('ENVIRONMENT') == 'production':
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': 5,
        'pool_timeout': 30,
        'pool_recycle': -1,
        'max_overflow': 2,
        'pool_pre_ping': True,
        'pool_reset_on_return': None,
        'creator': get_connection_creator()
    }
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql+pg8000://'
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///urls.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Initialize BigQuery client
bq_client = bigquery.Client() if os.getenv('ENVIRONMENT') == 'production' else None


class URL(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_url = db.Column(db.String(2048), nullable=False)
    short_code = db.Column(db.String(10), unique=True, nullable=False)
    clicks = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())


# Create tables - with error handling for production startup
with app.app_context():
    try:
        db.create_all()
        print("✅ Database tables created successfully")
    except Exception as e:
        print(f"⚠️ Database table creation failed: {e}")
        if os.getenv('ENVIRONMENT') == 'production':
            print("🔄 App will continue running - tables can be created via /api/init-db endpoint")
        else:
            raise  # Re-raise in development


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


def log_click_event(short_code, user_agent, ip_address):
    if not bq_client:
        return

    table_id = f"{os.getenv('GOOGLE_CLOUD_PROJECT')}.analytics.url_clicks"

    rows_to_insert = [{
        "short_code": short_code,
        "timestamp": datetime.now(datetime.UTC).isoformat(),
        "user_agent": user_agent,
        "ip_address": ip_address
    }]

    try:
        errors = bq_client.insert_rows_json(table_id, rows_to_insert)
        if errors:
            print(f"BigQuery insert errors: {errors}")
    except Exception as e:
        print(f"BigQuery error: {e}")


@app.route('/api/shorten', methods=['OPTIONS'])
def options_shorten():
    return '', 200


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
            'short_url': f'{get_base_url()}/{existing.short_code}',
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
        'short_url': f'{get_base_url()}/{short_code}',
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

    # Log to BigQuery
    log_click_event(
        short_code=short_code,
        user_agent=request.headers.get('User-Agent', ''),
        ip_address=request.remote_addr
    )

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


@app.route('/api/init-db', methods=['POST'])
def init_database():
    """Manual database initialization endpoint for production"""
    try:
        db.create_all()
        return jsonify({
            'status': 'success',
            'message': 'Database tables created successfully'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Database initialization failed: {str(e)}'
        }), 500


@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        db.session.execute(db.text('SELECT 1'))
        db_status = 'connected'
    except Exception as e:
        db_status = f'error: {str(e)}'
    
    return jsonify({
        'status': 'ok',
        'environment': os.getenv('ENVIRONMENT', 'development'),
        'database': db_status
    })


if __name__ == '__main__':
    app.run(debug=True, port=5001)