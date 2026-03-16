"""
Django settings for config project.
"""

from pathlib import Path
import os
from dotenv import load_dotenv
from datetime import timedelta

# Nạp các biến môi trường từ file .env vào hệ thống
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ==========================================
# 1. CORE SETTINGS (Đọc từ .env)
# ==========================================
# Gán một chuỗi vô hại nếu không có file .env, tuyệt đối không để lộ Secret Key thật
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-default-key-change-it-in-production')

DEBUG = os.getenv('DEBUG', 'False') == 'True'

allowed_hosts_env = os.getenv('ALLOWED_HOSTS', '*')
ALLOWED_HOSTS = allowed_hosts_env.split(',') if allowed_hosts_env else []


# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'users',
    'documents',
    'chat',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# ==========================================
# 2. CẤU HÌNH DATABASE (Bảo mật tuyệt đối)
# ==========================================
# PostgreSQL
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'Chat_bot'),      
        'USER': os.getenv('DB_USER', 'postgres'),           
        'PASSWORD': os.getenv('DB_PASSWORD', ''), # <--- ĐÃ XÓA TRẮNG
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

# MongoDB
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
MONGO_DB_NAME = os.getenv('MONGO_DB_NAME', 'textbook_db')

# Neo4j
NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', '') # <--- ĐÃ XÓA TRẮNG
NEO4J_AUTH = (NEO4J_USER, NEO4J_PASSWORD)

# ==========================================
# 3. CẤU HÌNH CLOUD & AI (Bảo mật tuyệt đối)
# ==========================================
# MinIO Storage
MINIO_STORAGE_ENDPOINT = os.getenv('MINIO_STORAGE_ENDPOINT', 'localhost:9000')
MINIO_STORAGE_ACCESS_KEY = os.getenv('MINIO_STORAGE_ACCESS_KEY', 'minioadmin')
MINIO_STORAGE_SECRET_KEY = os.getenv('MINIO_STORAGE_SECRET_KEY', 'minioadmin')
MINIO_STORAGE_BUCKET_NAME = os.getenv('MINIO_STORAGE_BUCKET_NAME', 'sach-giao-khoa')
MINIO_STORAGE_USE_HTTPS = os.getenv('MINIO_STORAGE_USE_HTTPS', 'False') == 'True'

# Google Gemini AI
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY', '') # <--- ĐÃ XÓA TRẮNG API KEY
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', GOOGLE_API_KEY)


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# ==========================================
# 4. STATIC & MEDIA FILES
# ==========================================
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles') 

MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'


# ==========================================
# 5. REST FRAMEWORK & CORS
# ==========================================
CORS_ALLOW_ALL_ORIGINS = True

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
}

AUTH_USER_MODEL = 'users.User'