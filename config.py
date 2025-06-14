# electronic_library/config.py

import os
from dotenv import load_dotenv

load_dotenv() # Загружаем переменные окружения из .env файла

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
                              'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance', 'electronic_library.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static/covers')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB limit for uploads
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    PAGINATION_PER_PAGE = 10
    POPULAR_BOOKS_PERIOD_MONTHS = 3 # Для варианта 4, популярные книги за последние 3 месяца
    MAX_VIEWS_PER_DAY = 10 # Максимальное количество просмотров для одной книги в день на пользователя/IP