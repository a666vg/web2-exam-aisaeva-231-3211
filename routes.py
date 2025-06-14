# electronic_library/routes.py

from flask import render_template, request, redirect, url_for, flash, send_from_directory, abort, make_response
from flask_login import login_user, logout_user, current_user, login_required # <-- Теперь login_required здесь!
from sqlalchemy import func, or_
from datetime import datetime, timedelta
import os
import hashlib
import bleach
import markdown
import pandas as pd
from io import StringIO
from functools import wraps # <-- Добавим functools.wraps сюда, так как декоратор будет здесь.

from extensions import db # db импортируем из extensions.py
from app import app # app импортируем из app.py, но без roles_required оттуда
from models import User, Book, Cover, Genre, Review, PageView
from forms import *
from config import Config

# Вспомогательная функция для проверки разрешенных расширений файлов
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# ОПРЕДЕЛЕНИЕ ДЕКОРАТОРА roles_required ТЕПЕРЬ НАХОДИТСЯ ЗДЕСЬ!
def roles_required(*roles):
    def wrapper(fn):
        @wraps(fn)
        @login_required # <-- login_required теперь определен в этом же файле
        def decorated_view(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Для выполнения данного действия необходимо пройти процедуру аутентификации.', 'warning')
                return redirect(url_for('login'))
            if current_user.role.name not in roles:
                flash('У вас недостаточно прав для выполнения данного действия.', 'danger')
                abort(403)
            return fn(*args, **kwargs)
        return decorated_view
    return wrapper


# --- Маршруты аутентификации ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(login=form.login.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            flash(f'Добро пожаловать, {user.get_full_name()}!', 'success')
            return redirect(next_page or url_for('index'))
        else:
            flash('Невозможно аутентифицироваться с указанными логином и паролем.', 'danger')
    return render_template('login.html', form=form, title='Вход')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('index'))

# --- Главная страница ---

@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    search_form = BookSearchForm(request.args)
    # Важно: для динамических choices в search_form, нужно переопределить их здесь,
    # так как форма создается до того, как Book будет полностью загружена
    search_form.publication_year.choices = [(y[0], str(y[0])) for y in db.session.query(Book.publication_year).distinct().order_by(Book.publication_year.desc()).all()]
    search_form.genres.choices = [(g.id, g.name) for g in Genre.query.order_by(Genre.name).all()]


    query = Book.query.order_by(Book.publication_year.desc())

    # Применяем фильтры поиска
    if search_form.validate():
        if search_form.title.data:
            query = query.filter(Book.title.ilike(f'%{search_form.title.data}%'))
        if search_form.genres.data:
            # Для фильтрации по жанрам через many-to-many связь
            query = query.join(Book.genres).filter(Genre.id.in_(search_form.genres.data))
        if search_form.publication_year.data:
            query = query.filter(Book.publication_year.in_(search_form.publication_year.data))
        if search_form.pages_from.data is not None:
            query = query.filter(Book.pages >= search_form.pages_from.data)
        if search_form.pages_to.data is not None:
            query = query.filter(Book.pages <= search_form.pages_to.data)
        if search_form.author.data:
            query = query.filter(Book.author.ilike(f'%{search_form.author.data}%'))

    books_pagination = query.paginate(page=page, per_page=app.config['PAGINATION_PER_PAGE'], error_out=False)
    books = books_pagination.items

    # --- Вариант 4: Популярные книги ---
    popular_books = []
    # Дата 3 месяца назад
    three_months_ago = datetime.datetime.now(datetime.timezone.utc) - timedelta(days=30 * app.config['POPULAR_BOOKS_PERIOD_MONTHS'])
    # Присоединяем Book к PageView и фильтруем по времени, группируем по книге
    popular_books_query = db.session.query(
        Book, func.count(PageView.id).label('view_count')
    ).join(PageView).filter(PageView.view_time >= three_months_ago).group_by(Book.id).order_by(func.count(PageView.id).desc()).limit(5).all()
    popular_books = [book for book, count in popular_books_query]


    # --- Вариант 4: Недавно просмотренные книги ---
    recently_viewed_books = []
    if current_user.is_authenticated:
        # Для аутентифицированного пользователя
        recent_views = PageView.query.filter_by(user_id=current_user.id).order_by(PageView.view_time.desc()).limit(5).all()
        recently_viewed_books = [pv.book for pv in recent_views if pv.book is not None] # Добавлена проверка на None, если книга была удалена
    else:
        # Для неаутентифицированного пользователя по IP
        user_ip = request.remote_addr
        recent_views = PageView.query.filter(PageView.ip_address == user_ip, PageView.user_id == None).order_by(PageView.view_time.desc()).limit(5).all()
        recently_viewed_books = [pv.book for pv in recent_views if pv.book is not None]

    return render_template('index.html',
                           books=books,
                           pagination=books_pagination,
                           search_form=search_form,
                           popular_books=popular_books,
                           recently_viewed_books=recently_viewed_books,
                           title='Главная')

# --- Маршруты для книг ---

@app.route('/book/add', methods=['GET', 'POST'])
@roles_required('admin') # Теперь roles_required импортируется из этого файла
def add_book():
    form = BookForm()
    # При добавлении книги поле обложки должно быть обязательным
    form.cover_file.validators = [FileRequired(), FileAllowed(app.config['ALLOWED_EXTENSIONS'], 'Только изображения!')]

    if form.validate_on_submit():
        # Начало транзакции
        try:
            # Санитизация описания
            sanitized_description = bleach.clean(markdown.markdown(form.short_description.data),
                                                 tags=list(bleach.sanitizer.ALLOWED_TAGS) + ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'em', 'strong', 'blockquote', 'code', 'pre', 'hr', 'br', 'a', 'img'],
                                                 attributes=bleach.sanitizer.ALLOWED_ATTRIBUTES)


            new_book = Book(
                title=form.title.data,
                short_description=sanitized_description,
                publication_year=form.publication_year.data,
                publisher=form.publisher.data,
                author=form.author.data,
                pages=form.pages.data
            )
            # Добавляем книгу, чтобы получить ID для обложки
            db.session.add(new_book)
            db.session.flush() # Получаем ID новой книги до коммита

            # Обработка обложки
            file = form.cover_file.data
            if file: # Проверяем, что файл был загружен (не пустая строка или None)
                file_content = file.read()
                if not file_content:
                    raise ValueError("Загруженный файл пуст.")
                md5_hash = hashlib.md5(file_content).hexdigest()
                file.seek(0) # Сбросить указатель файла после чтения для хэша

                existing_cover = Cover.query.filter_by(md5_hash=md5_hash).first()

                if existing_cover:
                    # Изображение уже существует, используем его
                    # Привязываем существующую обложку к новой книге
                    existing_cover.book_id = new_book.id
                    new_book.cover = existing_cover
                    # Удалять файл не нужно, так как он уже есть
                else:
                    # Сохраняем новую обложку
                    # Используем ID книги как часть имени файла, чтобы гарантировать уникальность и связь
                    # Получаем расширение файла
                    _, file_extension = os.path.splitext(file.filename)
                    filename = f"book_{new_book.id}{file_extension}"
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)

                    new_cover = Cover(
                        filename=filename,
                        mime_type=file.content_type,
                        md5_hash=md5_hash,
                        book=new_book
                    )
                    db.session.add(new_cover)

            # Добавляем жанры
            genres = Genre.query.filter(Genre.id.in_(form.genres.data)).all()
            new_book.genres.extend(genres)

            db.session.commit() # Коммит всех изменений
            flash('Книга успешно добавлена!', 'success')
            return redirect(url_for('view_book', book_id=new_book.id))
        except Exception as e:
            db.session.rollback() # Откатываем изменения в случае ошибки
            flash(f'При сохранении данных возникла ошибка: {e}. Проверьте корректность введённых данных.', 'danger')
            # Передаем форму с заполненными данными обратно
            return render_template('book_form.html', form=form, title='Добавить книгу', action='add')
    return render_template('book_form.html', form=form, title='Добавить книгу', action='add')


@app.route('/book/<int:book_id>/edit', methods=['GET', 'POST'])
@roles_required('admin', 'moderator')
def edit_book(book_id):
    book = db.session.get(Book, book_id)
    if not book:
        abort(404)

    form = BookForm(obj=book) # Заполняем форму данными из книги
    # Обложка не редактируется, поэтому поле необязательно
    form.cover_file.validators = [FileAllowed(app.config['ALLOWED_EXTENSIONS'], 'Только изображения!'), Optional()]

    # Устанавливаем выбранные жанры
    if request.method == 'GET':
        form.genres.data = [g.id for g in book.genres]

    if form.validate_on_submit():
        # Начало транзакции
        try:
            # Санитизация описания
            sanitized_description = bleach.clean(markdown.markdown(form.short_description.data),
                                                 tags=list(bleach.sanitizer.ALLOWED_TAGS) + ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'em', 'strong', 'blockquote', 'code', 'pre', 'hr', 'br', 'a', 'img'],
                                                 attributes=bleach.sanitizer.ALLOWED_ATTRIBUTES)

            book.title = form.title.data
            book.short_description = sanitized_description
            book.publication_year = form.publication_year.data
            book.publisher = form.publisher.data
            book.author = form.author.data
            book.pages = form.pages.data

            # Обновляем жанры
            book.genres = [] # Очищаем текущие жанры
            selected_genres = Genre.query.filter(Genre.id.in_(form.genres.data)).all()
            book.genres.extend(selected_genres)

            db.session.commit() # Коммит всех изменений
            flash('Книга успешно обновлена!', 'success')
            return redirect(url_for('view_book', book_id=book.id))
        except Exception as e:
            db.session.rollback() # Откатываем изменения в случае ошибки
            flash(f'При сохранении данных возникла ошибка: {e}. Проверьте корректность введённых данных.', 'danger')
            return render_template('book_form.html', form=form, title='Редактировать книгу', action='edit', book_id=book.id)

    return render_template('book_form.html', form=form, title='Редактировать книгу', action='edit', book_id=book.id)


@app.route('/book/<int:book_id>/delete', methods=['POST'])
@roles_required('admin')
def delete_book(book_id):
    book = db.session.get(Book, book_id)
    if not book:
        flash('Книга не найдена.', 'danger')
        return redirect(url_for('index'))

    try:
        # Удаление файла обложки из файловой системы
        if book.cover and os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], book.cover.filename)):
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], book.cover.filename))

        db.session.delete(book)
        db.session.commit()
        flash(f'Книга "{book.title}" успешно удалена!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'При удалении книги возникла ошибка: {e}', 'danger')
    return redirect(url_for('index'))


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/book/<int:book_id>')
def view_book(book_id):
    book = db.session.get(Book, book_id)
    if not book:
        abort(404)

    # --- Вариант 4: Учёт истории посещений ---
    user_ip = request.remote_addr
    now = datetime.datetime.now(datetime.timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = now

    # Проверяем количество просмотров сегодня для этого пользователя/IP
    if current_user.is_authenticated:
        view_count_today = PageView.query.filter_by(book_id=book_id, user_id=current_user.id).filter(PageView.view_time.between(today_start, today_end)).count()
    else:
        view_count_today = PageView.query.filter_by(book_id=book_id, ip_address=user_ip).filter(PageView.view_time.between(today_start, today_end), PageView.user_id == None).count()

    if view_count_today < app.config['MAX_VIEWS_PER_DAY']:
        new_view = PageView(
            book_id=book.id,
            user_id=current_user.id if current_user.is_authenticated else None,
            view_time=now,
            ip_address=user_ip
        )
        db.session.add(new_view)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Ошибка при сохранении просмотра: {e}") # Для дебага

    # Проверка, оставлял ли текущий пользователь рецензию
    user_review = None
    if current_user.is_authenticated:
        user_review = Review.query.filter_by(book_id=book.id, user_id=current_user.id).first()

    # Форма для новой рецензии (если пользователь имеет право и не оставлял рецензию)
    review_form = ReviewForm()
    if review_form.validate_on_submit(): # Если форма отправлена и рецензии нет
        if current_user.is_authenticated and current_user.role.name in ['user', 'moderator', 'admin']:
            if not user_review: # Дополнительная проверка, чтобы не добавлять вторую рецензию
                try:
                    print(f"DEBUG: Содержимое review_form.text.data ДО обработки: {review_form.text.data}")
                    # Санитизация текста рецензии
                    sanitized_review_text = bleach.clean(markdown.markdown(review_form.text.data),
                                                        tags=list(bleach.sanitizer.ALLOWED_TAGS) + ['p', 'br', 'em', 'strong', 'blockquote', 'code', 'pre'],
                                                        attributes=bleach.sanitizer.ALLOWED_ATTRIBUTES)
                    new_review = Review(
                        book_id=book.id,
                        user_id=current_user.id,
                        rating=review_form.rating.data,
                        text=sanitized_review_text
                    )
                    db.session.add(new_review)
                    db.session.commit()
                    flash('Ваша рецензия успешно добавлена!', 'success')
                    return redirect(url_for('view_book', book_id=book.id))
                except Exception as e:
                    db.session.rollback()
                    flash(f'Ошибка при добавлении рецензии: {e}', 'danger')
            else:
                flash('Вы уже оставили рецензию на эту книгу.', 'info')
        else:
            flash('У вас нет прав для добавления рецензии или вы не аутентифицированы.', 'danger')
            # Не перенаправляем на login, просто показываем сообщение и форму
            # return redirect(url_for('login')) # Или просто остаться на странице

    # Все рецензии для этой книги
    reviews = Review.query.filter_by(book_id=book.id).order_by(Review.created_at.desc()).all()


    return render_template('book_detail.html',
                           book=book,
                           reviews=reviews,
                           user_review=user_review,
                           review_form=review_form,
                           markdown=markdown.markdown, # Передаем функцию для преобразования Markdown
                           title=book.title)

# --- Маршруты для рецензий (на случай, если пользователь зайдёт на форму напрямую, а не через книгу) ---

@app.route('/book/<int:book_id>/add_review', methods=['GET', 'POST'])
@login_required
def add_review(book_id):
    book = db.session.get(Book, book_id)
    if not book:
        abort(404)

    if current_user.role.name not in ['user', 'moderator', 'admin']:
        flash('У вас недостаточно прав для добавления рецензии.', 'danger')
        return redirect(url_for('view_book', book_id=book.id))

    # Проверяем, оставлял ли пользователь уже рецензию
    existing_review = Review.query.filter_by(book_id=book.id, user_id=current_user.id).first()
    if existing_review:
        flash('Вы уже оставили рецензию на эту книгу.', 'info')
        return redirect(url_for('view_book', book_id=book.id))

    form = ReviewForm()
    if form.validate_on_submit():
        try:
            sanitized_text = bleach.clean(markdown.markdown(form.text.data),
                                          tags=list(bleach.sanitizer.ALLOWED_TAGS) + ['p', 'br', 'em', 'strong', 'blockquote', 'code', 'pre'],
                                          attributes=bleach.sanitizer.ALLOWED_ATTRIBUTES)
            new_review = Review(
                book_id=book.id,
                user_id=current_user.id,
                rating=form.rating.data,
                text=sanitized_text
            )
            db.session.add(new_review)
            db.session.commit()
            flash('Ваша рецензия успешно добавлена!', 'success')
            return redirect(url_for('view_book', book_id=book.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при сохранении рецензии: {e}', 'danger')
            return render_template('review_form.html', form=form, book=book, title=f'Добавить рецензию на "{book.title}"')

    return render_template('review_form.html', form=form, book=book, title=f'Добавить рецензию на "{book.title}"')


# --- Маршруты для Варианта 4: Статистика ---

@app.route('/statistics')
@roles_required('admin')
def statistics():
    active_tab = request.args.get('tab', 'journal') # По умолчанию вкладка "Журнал"
    page_journal = request.args.get('page_journal', 1, type=int)
    page_stats = request.args.get('page_stats', 1, type=int)

    filter_form = StatisticsFilterForm(request.args)

    # Журнал действий пользователей
    journal_query = PageView.query.order_by(PageView.view_time.desc())
    journal_pagination = journal_query.paginate(page=page_journal, per_page=app.config['PAGINATION_PER_PAGE'], error_out=False)

    # Статистика просмотра книг
    stats_query = db.session.query(
        Book.title, func.count(PageView.id).label('view_count')
    ).join(PageView).filter(PageView.user_id.isnot(None)) # Только аутентифицированные пользователи

    if filter_form.validate():
        if filter_form.date_from.data:
            from_date = datetime.strptime(filter_form.date_from.data, '%Y-%m-%d')
            stats_query = stats_query.filter(PageView.view_time >= from_date)
        if filter_form.date_to.data:
            to_date = datetime.strptime(filter_form.date_to.data, '%Y-%m-%d') + timedelta(days=1, microseconds=-1) # Включительно
            stats_query = stats_query.filter(PageView.view_time <= to_date)

    stats_query = stats_query.group_by(Book.id).order_by(func.count(PageView.id).desc())
    stats_pagination = stats_query.paginate(page=page_stats, per_page=app.config['PAGINATION_PER_PAGE'], error_out=False)


    return render_template('statistics.html',
                           active_tab=active_tab,
                           journal_pagination=journal_pagination,
                           stats_pagination=stats_pagination,
                           filter_form=filter_form,
                           title='Статистика')

@app.route('/export_journal_csv')
@roles_required('admin')
def export_journal_csv():
    all_views = PageView.query.order_by(PageView.view_time.desc()).all()
    data = []
    for i, view in enumerate(all_views):
        user_info = view.viewer.get_full_name() if view.viewer else "Неаутентифицированный пользователь"
        data.append([
            i + 1,
            user_info,
            view.book.title if view.book else "Книга удалена", # На случай, если книга была удалена
            view.view_time.strftime('%Y-%m-%d %H:%M:%S')
        ])

    df = pd.DataFrame(data, columns=['№', 'ФИО пользователя', 'Название книги', 'Дата и время просмотра'])
    sio = StringIO()
    df.to_csv(sio, index=False, encoding='utf-8')
    output = make_response(sio.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=journal_actions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8"
    return output

@app.route('/export_stats_csv')
@roles_required('admin')
def export_stats_csv():
    filter_form = StatisticsFilterForm(request.args)
    stats_query = db.session.query(
        Book.title, func.count(PageView.id).label('view_count')
    ).join(PageView).filter(PageView.user_id.isnot(None))

    if filter_form.validate():
        if filter_form.date_from.data:
            from_date = datetime.strptime(filter_form.date_from.data, '%Y-%m-%d')
            stats_query = stats_query.filter(PageView.view_time >= from_date)
        if filter_form.date_to.data:
            to_date = datetime.strptime(filter_form.date_to.data, '%Y-%m-%d') + timedelta(days=1, microseconds=-1)
            stats_query = stats_query.filter(PageView.view_time <= to_date)

    all_stats = stats_query.group_by(Book.id).order_by(func.count(PageView.id).desc()).all()

    data = []
    for i, (title, count) in enumerate(all_stats):
        data.append([i + 1, title, count])

    df = pd.DataFrame(data, columns=['№', 'Название книги', 'Количество просмотров'])
    sio = StringIO()
    df.to_csv(sio, index=False, encoding='utf-8')
    output = make_response(sio.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=book_views_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8"
    return output