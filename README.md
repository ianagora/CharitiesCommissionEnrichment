# Charity Commission Data Enrichment Platform

A full-stack platform for enriching entity data with Charity Commission records, building corporate ownership trees, and exporting comprehensive Excel reports.

## 🌐 URLs

- **Frontend (Cloudflare Pages)**: Deploy to get URL
- **Backend (Railway)**: Deploy to get URL
- **API Documentation**: `{backend-url}/docs` (in development mode)

## ✨ Features

### Core Functionality
- **Batch Upload**: Upload CSV or Excel files with entity names
- **Auto-Resolution**: AI-powered matching to Charity Commission records
- **Fuzzy Matching**: Intelligent name matching with confidence scores
- **Ownership Trees**: Recursive corporate ownership structure discovery
- **Multi-Tab Export**: Comprehensive Excel exports with styled formatting

### Security
- **JWT Authentication**: Secure token-based authentication
- **API Key Support**: Alternative authentication for integrations
- **Rate Limiting**: Protection against abuse
- **CORS Configuration**: Secure cross-origin requests

### Data Sources
- **Charity Commission England & Wales API**: Official charity data
- **OpenAI GPT-4o**: AI-powered entity matching (optional)

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Cloudflare Pages (Frontend)                  │
│                   TypeScript + Hono + Tailwind                  │
└─────────────────────────┬───────────────────────────────────────┘
                          │ HTTPS
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Railway (Backend)                           │
│                   FastAPI + Python 3.11                          │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Auth API    │  │  Batch API   │  │  Entity Resolution   │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ Export API   │  │ Ownership    │  │  Charity Commission  │  │
│  │              │  │ Tree Builder │  │  API Integration     │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Railway PostgreSQL                             │
└─────────────────────────────────────────────────────────────────┘
```

## 📁 Project Structure

```
webapp/
├── backend/                    # FastAPI Backend
│   ├── app/
│   │   ├── api/               # API routes
│   │   │   ├── auth.py        # Authentication endpoints
│   │   │   ├── batches.py     # Batch management
│   │   │   ├── entities.py    # Entity operations
│   │   │   └── exports.py     # Export functionality
│   │   ├── models/            # SQLAlchemy models
│   │   ├── schemas/           # Pydantic schemas
│   │   ├── services/          # Business logic
│   │   │   ├── auth.py        # Authentication service
│   │   │   ├── charity_commission.py
│   │   │   ├── entity_resolver.py
│   │   │   ├── ownership_builder.py
│   │   │   └── export_service.py
│   │   ├── config.py          # Configuration
│   │   ├── database.py        # Database setup
│   │   └── main.py            # FastAPI app
│   ├── alembic/               # Database migrations
│   ├── requirements.txt       # Python dependencies
│   ├── railway.toml           # Railway deployment config
│   ├── nixpacks.toml          # Nixpacks build config
│   ├── Dockerfile             # Docker build file
│   └── .env.example           # Environment template
│
├── frontend/                   # Hono/Vite Frontend
│   ├── src/
│   │   └── index.tsx          # Main Hono app
│   ├── public/
│   │   └── static/
│   │       └── app.js         # Frontend JavaScript
│   ├── vite.config.ts         # Vite configuration
│   ├── wrangler.jsonc         # Cloudflare config
│   └── .env.example           # Environment template
│
├── scripts/                    # Deployment scripts
│   ├── setup-local.sh         # Local development setup
│   ├── deploy-backend.sh      # Railway deployment
│   ├── deploy-frontend.sh     # Cloudflare deployment
│   └── push-to-github.sh      # GitHub push script
│
└── README.md                   # This file
```

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ (or Docker)
- Railway account (for backend deployment)
- Cloudflare account (for frontend deployment)

### Local Development

1. **Clone the repository**
```bash
git clone https://github.com/your-username/charity-data-enrichment-platform.git
cd charity-data-enrichment-platform
```

2. **Run setup script**
```bash
./scripts/setup-local.sh
```

3. **Start PostgreSQL** (using Docker)
```bash
docker run -d --name postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=charity_platform \
  -p 5432:5432 \
  postgres:15
```

4. **Configure backend environment**
```bash
cd backend
cp .env.example .env
# Edit .env with your settings
```

5. **Run database migrations**
```bash
cd backend
source venv/bin/activate
alembic upgrade head
```

6. **Start backend server**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

7. **Start frontend** (in new terminal)
```bash
cd frontend
npm run dev
```

8. **Open browser** at `http://localhost:5173`

## 🌐 Deployment

### Backend (Railway)

1. **Install Railway CLI**
```bash
npm install -g @railway/cli
railway login
```

2. **Create new project**
```bash
cd backend
railway init
```

3. **Add PostgreSQL**
```bash
railway add --plugin postgresql
```

4. **Set environment variables** in Railway dashboard:
   - `JWT_SECRET_KEY` - Generate with: `python -c "import secrets; print(secrets.token_urlsafe(64))"`
   - `OPENAI_API_KEY` - Your OpenAI API key (optional)
   - `CHARITY_COMMISSION_API_KEY` - Your Charity Commission API key
   - `CORS_ORIGINS` - Your Cloudflare Pages URL

5. **Deploy**
```bash
railway up
```

### Frontend (Cloudflare Pages)

1. **Login to Cloudflare**
```bash
cd frontend
npx wrangler login
```

2. **Build and deploy**
```bash
npm run build
npx wrangler pages deploy dist --project-name charity-data-enrichment
```

3. **Set environment variables** in Cloudflare dashboard:
   - `API_BASE_URL` - Your Railway backend URL

## 📚 API Reference

### Authentication

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/auth/register` | POST | Register new user |
| `/api/v1/auth/login` | POST | Login and get tokens |
| `/api/v1/auth/refresh` | POST | Refresh access token |
| `/api/v1/auth/me` | GET | Get current user |
| `/api/v1/auth/api-key` | POST | Generate API key |

### Batches

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/batches` | POST | Upload new batch |
| `/api/v1/batches` | GET | List all batches |
| `/api/v1/batches/{id}` | GET | Get batch details |
| `/api/v1/batches/{id}` | DELETE | Delete batch |
| `/api/v1/batches/{id}/process` | POST | Start processing |

### Entities

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/entities/batch/{batch_id}` | GET | List entities in batch |
| `/api/v1/entities/{id}` | GET | Get entity details |
| `/api/v1/entities/{id}/confirm` | POST | Confirm resolution |
| `/api/v1/entities/{id}/ownership-tree` | GET | Get ownership tree |

### Exports

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/exports/excel` | POST | Export to Excel |
| `/api/v1/exports/csv` | POST | Export to CSV |

## 🔧 Configuration

### Backend Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `JWT_SECRET_KEY` | Secret key for JWT tokens | Yes |
| `OPENAI_API_KEY` | OpenAI API key for AI matching | No |
| `CHARITY_COMMISSION_API_KEY` | Charity Commission API key | Yes |
| `CORS_ORIGINS` | Allowed origins (comma-separated) | Yes |
| `DEBUG` | Enable debug mode | No |

### Frontend Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `API_BASE_URL` | Backend API URL | Yes |

## 🔍 Troubleshooting

### Common Issues

**Database connection errors**
- Ensure PostgreSQL is running
- Check `DATABASE_URL` format: `postgresql+asyncpg://user:pass@host:5432/dbname`
- For Railway, the `DATABASE_URL` is auto-set

**CORS errors**
- Add your frontend URL to `CORS_ORIGINS` in backend
- Ensure the URL includes protocol (https://)

**API rate limiting**
- Wait 60 seconds between excessive requests
- Consider upgrading your API plan

**File upload errors**
- Check file size (max 10MB default)
- Ensure file format is CSV, XLSX, or XLS
- Verify the name column exists in your file

### Debug Mode

Enable debug mode for detailed logs:
```bash
# Backend
DEBUG=true uvicorn app.main:app --reload

# This enables:
# - Detailed error messages
# - API documentation at /docs
# - Request logging
```

## 🔐 Security Best Practices

1. **JWT Secret**: Generate a strong secret key and never commit it
2. **API Keys**: Store in environment variables, not in code
3. **CORS**: Only allow necessary origins
4. **Rate Limiting**: Configured at 60 requests/minute by default
5. **Input Validation**: All inputs are validated with Pydantic
6. **SQL Injection**: Protected by SQLAlchemy ORM
7. **Password Hashing**: Using bcrypt with salt

## 📄 License

MIT License - see LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## 📞 Support

- **Issues**: GitHub Issues
- **Documentation**: This README and API docs at `/docs`
- **Email**: support@example.com
