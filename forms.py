# electronic_library/forms.py

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import StringField, TextAreaField, IntegerField, SelectMultipleField, SelectField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, ValidationError, Optional
from models import Genre, Book # Импортируем Genre и Book для динамических выборок
import datetime
from extensions import db

class LoginForm(FlaskForm):
    login = StringField('Логин', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    remember_me = BooleanField('Запомнить меня')
    submit = SubmitField('Войти')

class BookForm(FlaskForm):
    title = StringField('Название', validators=[DataRequired(), Length(max=255)])
    short_description = TextAreaField('Краткое описание', validators=[DataRequired()])
    publication_year = IntegerField('Год издания', validators=[DataRequired(), NumberRange(min=1000, max=2100)]) # Год от 1000 до 2100
    publisher = StringField('Издательство', validators=[DataRequired(), Length(max=255)])
    author = StringField('Автор', validators=[DataRequired(), Length(max=255)])
    pages = IntegerField('Объём (в страницах)', validators=[DataRequired(), NumberRange(min=1)])
    genres = SelectMultipleField('Жанры', coerce=int, validators=[DataRequired()]) # coerce=int для преобразования значений в int
    cover_file = FileField('Обложка книги', validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Только изображения!'),
        Optional() # Сделаем необязательным, так как для редактирования обложка не требуется
    ])
    submit = SubmitField('Сохранить')

    def __init__(self, *args, **kwargs):
        super(BookForm, self).__init__(*args, **kwargs)
        # Динамически загружаем жанры из базы данных
        self.genres.choices = [(g.id, g.name) for g in Genre.query.order_by(Genre.name).all()]

class ReviewForm(FlaskForm):
    rating = SelectField('Оценка', coerce=int, validators=[DataRequired()],
                         choices=[(5, 'Отлично'), (4, 'Хорошо'), (3, 'Удовлетворительно'),
                                  (2, 'Неудовлетворительно'), (1, 'Плохо'), (0, 'Ужасно')])
    text = TextAreaField('Текст рецензии', validators=[DataRequired()])
    submit = SubmitField('Сохранить рецензию')

class BookSearchForm(FlaskForm):
    title = StringField('Название')
    genres = SelectMultipleField('Жанр', coerce=int)
    publication_year = SelectMultipleField('Год', coerce=int)
    pages_from = IntegerField('Объём от', validators=[Optional(), NumberRange(min=0)])
    pages_to = IntegerField('Объём до', validators=[Optional(), NumberRange(min=0)])
    author = StringField('Автор')
    submit = SubmitField('Найти')

    def __init__(self, *args, **kwargs):
        super(BookSearchForm, self).__init__(*args, **kwargs)
        self.genres.choices = [(g.id, g.name) for g in Genre.query.order_by(Genre.name).all()]
        # Получаем уникальные года из базы данных
        years = db.session.query(Book.publication_year).distinct().order_by(Book.publication_year.desc()).all()
        self.publication_year.choices = [(y[0], str(y[0])) for y in years]

class StatisticsFilterForm(FlaskForm):
    date_from = StringField('Дата от', validators=[Optional()])
    date_to = StringField('Дата до', validators=[Optional()])
    submit = SubmitField('Применить')

    def validate_date_from(self, field):
        if field.data:
            try:
                datetime.strptime(field.data, '%Y-%m-%d')
            except ValueError:
                raise ValidationError('Неверный формат даты. Используйте ГГГГ-ММ-ДД.')

    def validate_date_to(self, field):
        if field.data:
            try:
                datetime.strptime(field.data, '%Y-%m-%d')
            except ValueError:
                raise ValidationError('Неверный формат даты. Используйте ГГГГ-ММ-ДД.')

    def validate(self, extra_validators=None):
        if not super().validate(extra_validators):
            return False
        if self.date_from.data and self.date_to.data:
            from_date = datetime.strptime(self.date_from.data, '%Y-%m-%d')
            to_date = datetime.strptime(self.date_to.data, '%Y-%m-%d')
            if from_date > to_date:
                self.date_from.errors.append('Дата "от" не может быть позже даты "до".')
                return False
        return True