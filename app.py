# electronic_library/app.py

from flask import Flask, flash, redirect, url_for, request, abort, render_template
from flask_login import LoginManager, current_user # Здесь нужен только LoginManager и current_user
from config import Config
import os
# from functools import wraps # Этот импорт не нужен здесь, если roles_required перемещен в routes.py

# Импортируем db и login_manager из нового файла extensions.py
from extensions import db, login_manager

# Инициализация Flask-приложения
app = Flask(__name__, template_folder='templates/')
app.config.from_object(Config)

# Создание папки 'uploads' если она не существует
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Создание папки 'instance' если она не существует (для SQLite DB)
if not os.path.exists(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance')):
    os.makedirs(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance'))


# Привязываем SQLAlchemy к приложению
db.init_app(app)

# Привязываем Flask-Login к приложению
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Для выполнения данного действия необходимо пройти процедуру аутентификации.'
login_manager.login_message_category = 'warning'

# Теперь можно импортировать модели. Они будут импортировать 'db' из extensions.py.
from models import User, Role, Book, Review, PageView, Cover, Genre


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

from routes import *

# Обработчики ошибок
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(403)
def forbidden_access(e):
    flash('У вас недостаточно прав для выполнения данного действия.', 'danger')
    return redirect(url_for('index')) # <--- Убедитесь, что здесь url_for('index') корректен

# if __name__ == '__main__':
#     print("Зарегистрированные эндпоинты:")
#     for rule in app.url_map.iter_rules():
#         print(f"  {rule.endpoint}: {rule.rule}")
#     app.run(debug=False, host='0.0.0.0')




if __name__ == '__main__':
    print("Зарегистрированные эндпоинты:")
    for rule in app.url_map.iter_rules():
        print(f"  {rule.endpoint}: {rule.rule}")
    
    # Запуск на localhost с включенной отладкой
    app.run(debug=True)