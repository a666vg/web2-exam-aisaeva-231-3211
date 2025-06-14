import hashlib
from app import app
from extensions import db
from models import Role, User, Genre, Book, Cover
from werkzeug.security import generate_password_hash
from datetime import datetime
import os

with app.app_context():
    # Удаляем старую базу данных, если существует, для чистого запуска
    db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
    if os.path.exists(db_path):
        print(f"Удаление существующей базы данных: {db_path}")
        os.remove(db_path)
    else:
        instance_dir = os.path.dirname(db_path)
        if not os.path.exists(instance_dir):
            os.makedirs(instance_dir)

    print("Создание таблиц базы данных...")
    db.create_all()
    print("Таблицы созданы.")

    # Роли
    if not Role.query.first():
        admin_role = Role(name='admin', description='Суперпользователь')
        moderator_role = Role(name='moderator', description='Может редактировать данные книг')
        user_role = Role(name='user', description='Может оставлять рецензии')
        db.session.add_all([admin_role, moderator_role, user_role])
        db.session.commit()
        print("Роли добавлены.")

    # Администратор
    if not User.query.filter_by(login='admin').first():
        admin_role = Role.query.filter_by(name='admin').first()
        admin_user = User(login='admin', first_name='Иван', last_name='Иванов', patronymic='Иванович', role=admin_role)
        admin_user.set_password('adminpass')
        db.session.add(admin_user)
        db.session.commit()
        print("Тестовый администратор добавлен: login=admin, password=adminpass")

    # Пользователь
    if not User.query.filter_by(login='user').first():
        user_role = Role.query.filter_by(name='user').first()
        test_user = User(login='user', first_name='Петр', last_name='Петров', patronymic='Петрович', role=user_role)
        test_user.set_password('userpass')
        db.session.add(test_user)
        db.session.commit()
        print("Тестовый пользователь добавлен: login=user, password=userpass")

    # Модератор
    if not User.query.filter_by(login='moderator').first():
        moderator_role = Role.query.filter_by(name='moderator').first()
        test_moderator = User(login='moderator', first_name='Сергей', last_name='Сергеев', patronymic='Сергеевич', role=moderator_role)
        test_moderator.set_password('modpass')
        db.session.add(test_moderator)
        db.session.commit()
        print("Тестовый модератор добавлен: login=moderator, password=modpass")

    # Жанры
    test_genres = ['Фантастика', 'Детектив', 'Фэнтези', 'Научная литература', 'Классика', 'Роман', 'Исторический', 'Драма', 'Биография']
    for genre_name in test_genres:
        if not Genre.query.filter_by(name=genre_name).first():
            new_genre = Genre(name=genre_name)
            db.session.add(new_genre)
            db.session.commit()
            print(f"Жанр '{genre_name}' добавлен.")
        else:
            print(f"Жанр '{genre_name}' уже существует.")

    # Книги
    if not Book.query.first():
        # Получаем жанры из БД (гарантируем, что они существуют)
        fantasy = Genre.query.filter_by(name='Фантастика').first()
        detective = Genre.query.filter_by(name='Детектив').first()
        classic = Genre.query.filter_by(name='Классика').first()
        drama = Genre.query.filter_by(name='Драма').first()
        biography = Genre.query.filter_by(name='Биография').first()

        # Проверяем, что все нужные жанры найдены
        if not all([fantasy, detective, classic, drama, biography]):
            print("Ошибка: один или несколько жанров не найдены в базе данных.")
        else:
            def generate_md5(filename):
                return hashlib.md5(filename.encode()).hexdigest()

            books_data = [
                {
                    'title': 'Властелин Колец',
                    'description': 'Эпическая сага о Средиземье.',
                    'year': 1954,
                    'publisher': 'Allen & Unwin',
                    'author': 'Дж. Р. Р. Толкин',
                    'pages': 1178,
                    'genres': [fantasy, classic],
                    'cover_filename': '1_властелин_колец.png'
                },
                {
                    'title': 'Шерлок Холмс: Собака Баскервилей',
                    'description': 'Детектив о поместье Баскервилей.',
                    'year': 1902,
                    'publisher': 'George Newnes',
                    'author': 'Артур Конан Дойл',
                    'pages': 256,
                    'genres': [detective],
                    'cover_filename': '2_шерлок_холмс__собака_баскервилей.png'
                },
                {
                    'title': 'Дракула',
                    'description': 'Роман о вампирах.',
                    'year': 1897,
                    'publisher': 'Archibald Constable',
                    'author': 'Брэм Стокер',
                    'pages': 418,
                    'genres': [drama, classic],
                    'cover_filename': '3_дракула.png'
                },
                {
                    'title': 'Анна Каренина',
                    'description': 'Трагическая история любви.',
                    'year': 1877,
                    'publisher': 'Русский вестник',
                    'author': 'Лев Толстой',
                    'pages': 864,
                    'genres': [classic, drama],
                    'cover_filename': '4_анна_каренина.png'
                },
                {
                    'title': 'Стив Джобс',
                    'description': 'Биография основателя Apple.',
                    'year': 2011,
                    'publisher': 'Simon & Schuster',
                    'author': 'Уолтер Айзексон',
                    'pages': 656,
                    'genres': [biography],
                    'cover_filename': '5_стив_джобс.png'
                }
            ]

            for data in books_data:
                cover = Cover(
                    filename=data['cover_filename'],
                    mime_type='image/png',
                    md5_hash=generate_md5(data['cover_filename'])
                )
                book = Book(
                    title=data['title'],
                    short_description=data['description'],
                    publication_year=data['year'],
                    publisher=data['publisher'],
                    author=data['author'],
                    pages=data['pages'],
                    cover=cover
                )
                for genre in data['genres']:
                    book.genres.append(genre)
                db.session.add(book)

            try:
                db.session.commit()
                print("Добавлены 5 тестовых книг.")
            except Exception as e:
                db.session.rollback()
                print(f"Ошибка при добавлении книг: {e}")
    else:
        print("Книги уже существуют.")

    print("База данных инициализирована.")