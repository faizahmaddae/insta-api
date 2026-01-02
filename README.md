# 📸 Instagram API

A comprehensive, production-ready REST API that wraps [Instaloader](https://instaloader.github.io/) functionality for interacting with Instagram data programmatically.

## ✨ Features

- **🔐 Authentication** - Login/logout, session management, 2FA support
- **👤 Profiles** - Fetch profile information, followers, following, similar accounts
- **📷 Posts** - Retrieve posts, comments, likes, hashtags, reels, IGTV
- **📖 Stories** - Access user stories and highlights
- **🏠 Feed** - Browse feed, explore, saved posts, search
- **⬇️ Downloads** - Download posts, stories, and profile pictures
- **⚡ Async** - Non-blocking operations for high performance
- **🛡️ Rate Limiting** - Built-in protection against abuse
- **🔑 API Key Auth** - Optional security layer
- **📝 OpenAPI Docs** - Interactive API documentation
- **🐳 Docker Ready** - Easy containerized deployment

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- pip or pipenv

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/instagram-api.git
   cd instagram-api
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

5. **Run the server**
   ```bash
   uvicorn app.main:app --reload
   ```

6. **Open API docs**
   
   Navigate to [http://localhost:8000/docs](http://localhost:8000/docs)

## 🐳 Docker Deployment

### Using Docker Compose (Recommended)

```bash
# Production mode
docker compose up -d

# Development mode with hot reload
docker compose --profile dev up

# View logs
docker compose logs -f
```

### Using Docker directly

```bash
# Build image
docker build -t instagram-api .

# Run container
docker run -d \
  -p 8000:8000 \
  -e DEBUG=false \
  -v instagram_sessions:/app/sessions \
  --name instagram-api \
  instagram-api
```

## 📖 API Documentation

### ⚠️ Important: Instagram Authentication Requirements

Instagram has significantly restricted unauthenticated access. Here's what works without login:

| Endpoint | Auth Required? |
|----------|---------------|
| Profile info (`/profiles/{username}`) | ❌ No |
| Profile posts (`/posts/profile/{username}`) | ❌ No |
| Direct post by shortcode (`/posts/{shortcode}`) | ✅ **Yes** |
| Stories | ✅ **Yes** |
| Followers/Following | ✅ **Yes** |
| Feed operations | ✅ **Yes** |
| Search | ❌ No (limited) |

### Authentication

**Login once and the API will remember your session!**

```bash
# Login (creates a session file that persists across restarts)
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "your_username", "password": "your_password"}'

# Check session status
curl http://localhost:8000/api/v1/auth/status

# List available saved sessions
curl http://localhost:8000/api/v1/auth/sessions

# Load a previously saved session (if you have multiple accounts)
curl -X POST http://localhost:8000/api/v1/auth/load-session \
  -H "Content-Type: application/json" \
  -d '{"username": "previously_saved_username"}'
```

> **Note**: After logging in once, the session is saved to disk. On server restart, the session is automatically loaded!

### Profiles

```bash
# Get profile by username
curl http://localhost:8000/api/v1/profiles/instagram

# Get followers (requires login)
curl http://localhost:8000/api/v1/profiles/instagram/followers?limit=10

# Get following (requires login)
curl http://localhost:8000/api/v1/profiles/instagram/following?limit=10
```

### Posts

```bash
# Get post by shortcode
curl http://localhost:8000/api/v1/posts/CyAbcd1234

# Get profile posts
curl http://localhost:8000/api/v1/posts/profile/instagram?limit=10

# Get hashtag posts
curl http://localhost:8000/api/v1/posts/hashtag/photography?limit=10
```

### Stories

```bash
# Get user stories (requires login)
curl http://localhost:8000/api/v1/stories/user/instagram

# Get highlights (requires login)
curl http://localhost:8000/api/v1/stories/highlights/instagram
```

### Downloads

```bash
# Download post media
curl -X POST http://localhost:8000/api/v1/download/post/CyAbcd1234

# Download profile picture
curl -X POST http://localhost:8000/api/v1/download/profile-picture/instagram
```

## ⚙️ Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_NAME` | Application name | `Instagram API` |
| `APP_VERSION` | Version number | `1.0.0` |
| `DEBUG` | Enable debug mode | `true` |
| `API_PREFIX` | URL prefix for routes | `/api/v1` |
| `INSTAGRAM_USERNAME` | Auto-login username | - |
| `INSTAGRAM_PASSWORD` | Auto-login password | - |
| `SESSION_DIR` | Session files directory | `./sessions` |
| `DOWNLOAD_DIR` | Downloaded media directory | `./downloads` |
| `RATE_LIMIT_REQUESTS` | Max requests per window | `60` |
| `RATE_LIMIT_WINDOW` | Rate limit window (seconds) | `60` |
| `API_KEY` | Optional API key | - |
| `CORS_ORIGINS` | Allowed CORS origins | `*` |
| `LOG_LEVEL` | Logging level | `INFO` |

## 🏗️ Project Structure

```
instagram-api/
├── app/
│   ├── core/
│   │   ├── config.py       # Configuration management
│   │   ├── exceptions.py   # Custom exceptions
│   │   └── logging.py      # Logging setup
│   ├── middleware/
│   │   ├── auth.py         # API key authentication
│   │   ├── error_handlers.py  # Exception handlers
│   │   ├── logging.py      # Request logging
│   │   └── rate_limit.py   # Rate limiting
│   ├── models/
│   │   ├── auth.py         # Authentication models
│   │   ├── common.py       # Shared models
│   │   ├── post.py         # Post models
│   │   ├── profile.py      # Profile models
│   │   └── story.py        # Story models
│   ├── routes/
│   │   ├── auth.py         # Auth endpoints
│   │   ├── download.py     # Download endpoints
│   │   ├── feed.py         # Feed endpoints
│   │   ├── posts.py        # Posts endpoints
│   │   ├── profiles.py     # Profiles endpoints
│   │   └── stories.py      # Stories endpoints
│   ├── services/
│   │   ├── converters.py   # Data converters
│   │   └── instaloader_service.py  # Instaloader wrapper
│   └── main.py             # Application entry point
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## 🔒 Security Considerations

1. **Never commit credentials** - Use environment variables
2. **Enable API key** in production - Set `API_KEY` in .env
3. **Use HTTPS** - Deploy behind a reverse proxy with SSL
4. **Rate limiting** - Adjust limits based on your needs
5. **Session security** - Protect session files, they grant account access

## ⚠️ Disclaimer

This project is for educational purposes only. Please respect Instagram's Terms of Service:

- Don't use this for automated data collection at scale
- Don't violate users' privacy
- Don't use for spam or malicious purposes
- Rate limit your requests to avoid IP bans

The maintainers are not responsible for any misuse of this software.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- [Instaloader](https://instaloader.github.io/) - The amazing library this API wraps
- [FastAPI](https://fastapi.tiangolo.com/) - The web framework used
- [Pydantic](https://docs.pydantic.dev/) - Data validation library
