# SPDX-License-Identifier: MIT

import random
import string
from typing import cast


from cloudflare_error_page import ErrorPageParams
from flask import (
    Blueprint,
    current_app,
    request,
    abort,
    redirect,
    url_for,
)

from . import (
    db,
    limiter,
    models,
)
from .utils import (
    render_extended_template,
    sanitize_page_param_links,
)

bp = Blueprint('share', __name__, url_prefix='/')
bp_short = Blueprint('share_short', __name__, url_prefix='/')

rand_charset = string.ascii_lowercase + string.digits


def get_rand_name(digits=8):
    return ''.join(random.choice(rand_charset) for _ in range(digits))


@bp.post('/create')
@limiter.limit('20 per minute')
@limiter.limit('500 per hour')
def create():
    if len(request.data) > 4096:
        abort(413)

    # Simple CSRF check
    sec_fetch_site = request.headers.get('Sec-Fetch-Site')
    if sec_fetch_site is not None and sec_fetch_site != 'same-origin':
        return {
            'status': 'failed',
            'message': 'CSRF check failed (Sec-Fetch-Site)',
        }, 403

    # Accessing request.json raises 415 error if Content-Type is not application/json. This also prevents CSRF requests.
    # See https://developer.mozilla.org/en-US/docs/Web/Security/Attacks/CSRF#avoiding_simple_requests
    params = request.json['parameters']  # throws KeyError

    # TODO: strip unused params
    try:
        item = models.Item()
        digits = current_app.config.get('SHARE_LINK_DIGITS', 7)
        item.name = get_rand_name(digits)
        item.params = params
        db.session.add(item)
        db.session.commit()
    except:
        db.session.rollback()
        return {
            'status': 'failed',
        }
    return {
        'status': 'ok',
        'name': item.name,
        'url': request.host_url[:-1] + url_for('share_short.get', name=item.name),
        # TODO: better way to handle this
    }


@bp_short.get('/<name>')
def get(name: str):
    accept = request.headers.get('Accept', '')
    is_json = 'application/json' in accept

    item = db.session.query(models.Item).filter_by(name=name).first()
    if not item:
        if is_json:
            return {'status': 'notfound'}
        else:
            return abort(404)
    params = cast(ErrorPageParams, item.params)
    params.pop('time', None)
    params.pop('ray_id', None)
    params.pop('client_ip', None)

    if is_json:
        return {
            'status': 'ok',
            'parameters': params,
        }
    else:
        params['creator_info'] = {
            'hidden': False,
            'text': 'CF Error Page Editor',
            'link': request.host_url[:-1] + url_for('editor.index') + f'#from={name}',
        }
        sanitize_page_param_links(params)
        return render_extended_template(params=params, allow_html=False)


@bp.get('/<name>')
def get_redir(name: str):
    short_share_url = current_app.config.get('SHORT_SHARE_URL', False)
    if short_share_url:
        return redirect(f'../{name}', code=308)
    else:
        return get(name=name)
