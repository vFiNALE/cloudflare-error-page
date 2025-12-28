# SPDX-License-Identifier: MIT

import os
from pathlib import Path
import secrets
import string
import tomllib

from flask import Flask, redirect, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

root_dir = Path(__file__).parent.parent.parent.parent


class Base(DeclarativeBase):
    pass


db: SQLAlchemy = SQLAlchemy(
    model_class=Base,
    session_options={
        # 'autobegin': False,
        # 'expire_on_commit': False,
    },
)

limiter: Limiter = Limiter(
    key_func=get_remote_address,  # Uses client's IP address by default
)
static_dir: str | None = None


def _generate_secret(length=32) -> str:
    characters = string.ascii_letters + string.digits  # A-Z, a-z, 0-9
    return ''.join(secrets.choice(characters) for _ in range(length))


def _initialize_app_config(app: Flask):
    global static_dir
    if app.config.get('BEHIND_PROXY', True):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
    secret_key = app.config.get('SECRET_KEY', '')
    if secret_key:
        app.secret_key = secret_key
    else:
        app.logger.info('Using generated secret')
        app.secret_key = _generate_secret()

    app.config['SQLALCHEMY_DATABASE_URI'] = app.config.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///example.db')
    if app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite'):
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'isolation_level': 'SERIALIZABLE',
            # "execution_options": {"autobegin": False}
        }
    static_dir = os.path.join(app.instance_path, app.config.get('STATIC_DIR', '../../web/dist'))
    app.logger.info(f'Static directory: {static_dir}')


def create_app(test_config=None) -> Flask:
    instance_path = os.getenv('INSTANCE_PATH')
    if instance_path is not None:
        instance_path = os.path.abspath(instance_path)
        os.makedirs(instance_path, exist_ok=True)
        print(f'App instance path: {instance_path}')

    app = Flask(__name__, instance_path=instance_path, instance_relative_config=True)
    app.config.from_file('config.toml', load=tomllib.load, text=False)
    _initialize_app_config(app)

    from . import utils  # noqa: F401
    from . import models  # noqa: F401
    from . import examples
    from . import editor
    from . import share

    db.init_app(app)
    limiter.init_app(app)

    with app.app_context():
        db.create_all()

    @app.route('/')
    def index():
        return redirect(url_for('editor.index'))

    @app.route('/health')
    def health():
        return '', 204

    url_prefix = app.config.get('URL_PREFIX', '')
    short_share_url = app.config.get('SHORT_SHARE_URL', False)
    app.register_blueprint(editor.bp, url_prefix=f'{url_prefix}/editor')
    app.register_blueprint(examples.bp, url_prefix=f'{url_prefix}/examples')
    app.register_blueprint(share.bp, url_prefix=f'{url_prefix}/s')
    app.register_blueprint(share.bp_short, url_prefix=f'{url_prefix}' + ('' if short_share_url else '/s'))

    return app


__all__ = ['create_app']
