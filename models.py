

from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
# Импортируем db из extensions.py
from extensions import db

# Ассоциативная таблица для связи Many-to-Many между книгами и жанрами
book_genres = db.Table('book_genres',
    db.Column('book_id', db.Integer, db.ForeignKey('books.id', ondelete='CASCADE'), primary_key=True),
    db.Column('genre_id', db.Integer, db.ForeignKey('genres.id', ondelete='CASCADE'), primary_key=True)
)

class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    description = db.Column(db.Text)

    users = db.relationship('User', backref='role', lazy=True)

    def __repr__(self):
        return f"<Role {self.name}>"

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    last_name = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(255), nullable=False)
    patronymic = db.Column(db.String(255))
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)

    reviews = db.relationship('Review', backref='author', lazy=True)
    page_views = db.relationship('PageView', backref='viewer', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_full_name(self):
        full_name = f"{self.first_name} {self.last_name}"
        if self.patronymic:
            full_name += f" {self.patronymic}"
        return full_name

    def __repr__(self):
        return f"<User {self.login}>"

class Genre(db.Model):
    __tablename__ = 'genres'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)

    def __repr__(self):
        return f"<Genre {self.name}>"

class Book(db.Model):
    __tablename__ = 'books'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    short_description = db.Column(db.Text, nullable=False)
    publication_year = db.Column(db.Integer, nullable=False)
    publisher = db.Column(db.String(255), nullable=False)
    author = db.Column(db.String(255), nullable=False)
    pages = db.Column(db.Integer, nullable=False)

    genres = db.relationship('Genre', secondary=book_genres, lazy='subquery', backref=db.backref('books', lazy=True))
    cover = db.relationship('Cover', backref='book', lazy=True, uselist=False)
    reviews = db.relationship('Review', backref='book', lazy=True)
    page_views = db.relationship('PageView', backref='book', lazy=True)

    def get_average_rating(self):
        if self.reviews:
            return round(sum(review.rating for review in self.reviews) / len(self.reviews), 1)
        return 0.0

    def get_review_count(self):
        return len(self.reviews)

    def __repr__(self):
        return f"<Book {self.title}>"

class Cover(db.Model):
    __tablename__ = 'covers'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(255), nullable=False)
    md5_hash = db.Column(db.String(32), unique=True, nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id', ondelete='CASCADE'), nullable=False)

    def __repr__(self):
        return f"<Cover {self.filename}>"

class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.TIMESTAMP, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Review for Book {self.book_id} by User {self.user_id}>"

class PageView(db.Model):
    __tablename__ = 'page_views'
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    view_time = db.Column(db.TIMESTAMP, default=datetime.utcnow, nullable=False)
    ip_address = db.Column(db.String(45), nullable=False)

    def __repr__(self):
        return f"<PageView Book: {self.book_id}, User: {self.user_id}, IP: {self.ip_address}, Time: {self.view_time}>"