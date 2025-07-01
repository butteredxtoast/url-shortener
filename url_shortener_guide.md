# URL Shortener - Full Stack Development Guide

## Project Overview
Build a complete URL shortener application using modern web technologies. This project serves as a practical introduction to the company's tech stack through a focused, two-day implementation.

## Technology Stack
- **Backend**: Python 3.9+ with Flask
- **Frontend**: Vue 3 with TypeScript
- **Database**: Cloud SQL (PostgreSQL) 
- **Cloud Platform**: Google Cloud Platform
- **Analytics**: BigQuery
- **Hosting**: Firebase Hosting (frontend) + Cloud Run (backend)

---

## Phase 1: Flask Backend Foundation (4-6 hours)

### Step 1.1: Project Setup
```bash
# Create project structure
mkdir url-shortener && cd url-shortener
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install flask flask-sqlalchemy python-dotenv requests
```

### Step 1.2: Core Flask Application
Create `app.py`:
```python
from flask import Flask, request, jsonify, redirect
from flask_sqlalchemy import SQLAlchemy
import string
import random
import re
from urllib.parse import urlparse

app = Flask(__name__)
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
            'short_url': f'http://localhost:5000/{existing.short_code}',
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
        'short_url': f'http://localhost:5000/{short_code}',
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
    app.run(debug=True)
```

### Step 1.3: Test Backend
```bash
# Run the application
python app.py

# Test with curl
curl -X POST http://localhost:5000/api/shorten \
  -H "Content-Type: application/json" \
  -d '{"url": "https://google.com"}'
```

---

## Phase 2: Google Cloud Integration (2-3 hours)

### Step 2.1: Cloud SQL Setup
```bash
# Install Google Cloud CLI and authenticate
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Create Cloud SQL instance
gcloud sql instances create url-shortener-db \
    --database-version=POSTGRES_13 \
    --tier=db-f1-micro \
    --region=us-central1

# Create database and user
gcloud sql databases create urlshortener --instance=url-shortener-db
gcloud sql users create appuser --instance=url-shortener-db --password=your-secure-password
```

### Step 2.2: Update Flask for Cloud SQL
Install additional dependencies:
```bash
pip install psycopg2-binary cloud-sql-python-connector
```

Update `app.py` configuration:
```python
import os
from google.cloud.sql.connector import Connector

# Add after imports
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
        
        return getconn
    else:
        return 'sqlite:///urls.db'

# Update Flask config
if os.getenv('ENVIRONMENT') == 'production':
    app.config['SQLALCHEMY_DATABASE_URI'] = init_connection_pool()
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///urls.db'
```

### Step 2.3: Deploy to Cloud Run
Create `requirements.txt`:
```txt
Flask==2.3.3
Flask-SQLAlchemy==3.0.5
psycopg2-binary==2.9.7
google-cloud-sql-connector==1.4.3
python-dotenv==1.0.0
requests==2.31.0
```

Create `Dockerfile`:
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 app:app
```

Deploy:
```bash
pip install gunicorn
gcloud run deploy url-shortener-api \
    --source . \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated
```

---

## Phase 3: Vue.js Frontend with shadcn-vue (3-4 hours)

### Step 3.1: Vue Project Setup
```bash
npm create vue@latest url-shortener-frontend
cd url-shortener-frontend
# Select: TypeScript, Router, ESLint
npm install axios

# Install shadcn-vue
npx shadcn-vue@latest init
# Choose: Default style, Neutral base color, CSS variables for colors
```

### Step 3.2: Install Required shadcn-vue Components
```bash
npx shadcn-vue@latest add button
npx shadcn-vue@latest add input
npx shadcn-vue@latest add card
npx shadcn-vue@latest add alert
npx shadcn-vue@latest add badge
npx shadcn-vue@latest add separator
```

### Step 3.3: Main Application Component
Update `src/App.vue`:
```vue
<template>
  <div id="app" class="min-h-screen bg-background">
    <header class="border-b">
      <div class="container mx-auto px-4 py-6">
        <h1 class="text-3xl font-bold text-center">URL Shortener</h1>
        <p class="text-muted-foreground text-center mt-2">
          Transform long URLs into short, shareable links
        </p>
      </div>
    </header>
    
    <main class="container mx-auto px-4 py-8 max-w-2xl">
      <UrlShortener @url-shortened="handleUrlShortened" />
      <UrlStats v-if="lastShortenedCode" :shortCode="lastShortenedCode" class="mt-8" />
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import UrlShortener from './components/UrlShortener.vue'
import UrlStats from './components/UrlStats.vue'

const lastShortenedCode = ref<string>('')

const handleUrlShortened = (shortCode: string) => {
  lastShortenedCode.value = shortCode
}
</script>
```

### Step 3.4: URL Shortener Component
Create `src/components/UrlShortener.vue`:
```vue
<template>
  <Card>
    <CardHeader>
      <CardTitle>Shorten Your URL</CardTitle>
      <CardDescription>
        Enter a long URL below to create a shortened version
      </CardDescription>
    </CardHeader>
    
    <CardContent class="space-y-4">
      <form @submit.prevent="shortenUrl" class="flex gap-2">
        <Input
          v-model="originalUrl"
          type="url"
          placeholder="https://example.com/very/long/url..."
          :disabled="loading"
          class="flex-1"
        />
        <Button 
          type="submit" 
          :disabled="loading || !originalUrl"
        >
          <Loader2 v-if="loading" class="w-4 h-4 mr-2 animate-spin" />
          {{ loading ? 'Shortening...' : 'Shorten' }}
        </Button>
      </form>

      <Alert v-if="error" variant="destructive">
        <AlertCircle class="h-4 w-4" />
        <AlertTitle>Error</AlertTitle>
        <AlertDescription>{{ error }}</AlertDescription>
      </Alert>

      <Card v-if="result" class="border-green-200 bg-green-50">
        <CardHeader>
          <CardTitle class="text-green-800 flex items-center gap-2">
            <CheckCircle class="h-5 w-5" />
            URL Shortened Successfully!
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div class="flex gap-2">
            <Input 
              :value="result.short_url" 
              readonly 
              class="flex-1"
              ref="resultInput"
            />
            <Button 
              @click="copyToClipboard" 
              variant="outline"
              size="sm"
            >
              <Copy v-if="!copied" class="w-4 h-4 mr-2" />
              <Check v-else class="w-4 h-4 mr-2" />
              {{ copied ? 'Copied!' : 'Copy' }}
            </Button>
          </div>
        </CardContent>
      </Card>
    </CardContent>
  </Card>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import axios from 'axios'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Loader2, AlertCircle, CheckCircle, Copy, Check } from 'lucide-vue-next'

interface ShortenResponse {
  short_url: string
  short_code: string
}

const emit = defineEmits<{
  'url-shortened': [shortCode: string]
}>()

const originalUrl = ref('')
const loading = ref(false)
const error = ref('')
const result = ref<ShortenResponse | null>(null)
const copied = ref(false)
const resultInput = ref<HTMLInputElement>()

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:5000'

const shortenUrl = async () => {
  if (!originalUrl.value) return
  
  loading.value = true
  error.value = ''
  result.value = null
  copied.value = false

  try {
    const response = await axios.post<ShortenResponse>(`${API_BASE}/api/shorten`, {
      url: originalUrl.value
    })
    
    result.value = response.data
    emit('url-shortened', response.data.short_code)
  } catch (err: any) {
    error.value = err.response?.data?.error || 'Failed to shorten URL'
  } finally {
    loading.value = false
  }
}

const copyToClipboard = async () => {
  if (!result.value) return
  
  try {
    await navigator.clipboard.writeText(result.value.short_url)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch (err) {
    // Fallback for older browsers
    if (resultInput.value) {
      resultInput.value.select()
      document.execCommand('copy')
      copied.value = true
      setTimeout(() => { copied.value = false }, 2000)
    }
  }
}
</script>
```

### Step 3.5: Stats Component
Create `src/components/UrlStats.vue`:
```vue
<template>
  <Card v-if="stats">
    <CardHeader>
      <CardTitle class="flex items-center gap-2">
        <BarChart3 class="h-5 w-5" />
        URL Statistics
      </CardTitle>
      <CardDescription>
        Analytics for your shortened URL
      </CardDescription>
    </CardHeader>
    
    <CardContent class="space-y-4">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="space-y-2">
          <div class="text-sm font-medium text-muted-foreground">Original URL</div>
          <div class="text-sm break-all bg-muted p-2 rounded">
            {{ stats.original_url }}
          </div>
        </div>
        
        <div class="space-y-2">
          <div class="text-sm font-medium text-muted-foreground">Short Code</div>
          <Badge variant="secondary" class="font-mono">
            {{ stats.short_code }}
          </Badge>
        </div>
      </div>

      <Separator />

      <div class="grid grid-cols-2 gap-4">
        <div class="text-center">
          <div class="text-2xl font-bold text-primary">{{ stats.clicks }}</div>
          <div class="text-sm text-muted-foreground">Total Clicks</div>
        </div>
        
        <div class="text-center">
          <div class="text-sm font-medium">{{ formatDate(stats.created_at) }}</div>
          <div class="text-sm text-muted-foreground">Created</div>
        </div>
      </div>
    </CardContent>
  </Card>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import axios from 'axios'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { BarChart3 } from 'lucide-vue-next'

interface UrlStats {
  short_code: string
  original_url: string
  clicks: number
  created_at: string
}

const props = defineProps<{
  shortCode: string
}>()

const stats = ref<UrlStats | null>(null)
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:5000'

const fetchStats = async () => {
  if (!props.shortCode) return
  
  try {
    const response = await axios.get<UrlStats>(`${API_BASE}/api/stats/${props.shortCode}`)
    stats.value = response.data
  } catch (err) {
    console.error('Failed to fetch stats:', err)
  }
}

const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

watch(() => props.shortCode, fetchStats, { immediate: true })
</script>
```

### Step 3.6: Install Lucide Icons
```bash
npm install lucide-vue-next
```

### Step 3.5: Environment Configuration
Create `.env`:
```bash
VITE_API_URL=https://your-cloud-run-url
```

---

## Phase 4: Firebase Hosting & BigQuery Analytics (2-3 hours)

### Step 4.1: Firebase Setup
```bash
npm install -g firebase-tools
firebase login
firebase init hosting
# Select existing project or create new one
# Set public directory to 'dist'
# Configure as SPA: Yes
```

### Step 4.2: Build and Deploy Frontend
```bash
npm run build
firebase deploy
```

### Step 4.3: BigQuery Integration
Add to Flask backend in `app.py`:
```python
from google.cloud import bigquery
import json
from datetime import datetime

# Initialize BigQuery client
bq_client = bigquery.Client() if os.getenv('ENVIRONMENT') == 'production' else None

def log_click_event(short_code, user_agent, ip_address):
    if not bq_client:
        return
    
    table_id = f"{os.getenv('GOOGLE_CLOUD_PROJECT')}.analytics.url_clicks"
    
    rows_to_insert = [{
        "short_code": short_code,
        "timestamp": datetime.utcnow().isoformat(),
        "user_agent": user_agent,
        "ip_address": ip_address
    }]
    
    try:
        errors = bq_client.insert_rows_json(table_id, rows_to_insert)
        if errors:
            print(f"BigQuery insert errors: {errors}")
    except Exception as e:
        print(f"BigQuery error: {e}")

# Update redirect_url function
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
```

---

## Testing Checklist

### Backend Tests
- [ ] URL shortening with valid URLs
- [ ] URL validation (reject invalid URLs)
- [ ] Duplicate URL handling
- [ ] Short code uniqueness
- [ ] Click tracking functionality
- [ ] Stats endpoint accuracy

### Frontend Tests
- [ ] URL input validation
- [ ] Loading states display
- [ ] Error handling
- [ ] Copy to clipboard functionality
- [ ] Responsive design
- [ ] Stats display updates

### Integration Tests
- [ ] End-to-end URL shortening flow
- [ ] Redirect functionality
- [ ] Analytics data collection
- [ ] Cross-browser compatibility

---

## Deployment URLs
- **Frontend**: `https://your-project.web.app`
- **Backend API**: `https://url-shortener-api-[hash]-uc.a.run.app`

## Next Steps
1. Add user authentication with Firebase Auth
2. Implement custom domains for short URLs
3. Add URL expiration functionality
4. Create analytics dashboard with BigQuery data
5. Implement rate limiting and abuse prevention