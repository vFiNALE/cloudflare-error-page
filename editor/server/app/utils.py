import json
import os
import re
from typing import Any
from pathlib import Path

from cloudflare_error_page import (
    ErrorPageParams,
    base_template as base_template,
    render as render_cf_error_page,
)
from flask import current_app, request
from jinja2 import Environment, select_autoescape

env = Environment(
    autoescape=select_autoescape(),
    trim_blocks=True,
    lstrip_blocks=True,
)
template = env.from_string("""{% extends base %}

{% block html_head %}
{% if page_icon_url %}
{% if page_icon_type %}
<link rel="icon" href="{{ page_icon_url }}" type="{{ page_icon_type }}">
{% else %}
<link rel="icon" href="{{ page_icon_url }}">
{% endif %}
{% endif %}

<meta property="og:type" content="website" />
<meta property="og:site_name" content="moe::virt" />
<meta property="og:title" content="{{ html_title }}" />
<meta property="og:url" content="{{ page_url }}" />
<meta property="og:description" content="{{ page_description }}" />
{% if page_image_url %}
<meta property="og:image" content="{{ page_image_url }}" />
{% endif %}

<meta property="twitter:card" content="summary" />
<meta property="twitter:site" content="moe::virt" />
<meta property="twitter:title" content="{{ html_title }}" />
<meta property="twitter:description" content="{{ page_description }}" />
{% if page_image_url %}
<meta property="twitter:image" content="{{ page_image_url }}" />
{% endif %}
{% endblock %}
""")


loc_data: dict = None


def read_loc_file(path: str):
    try:
        with open(os.path.join(Path(__file__).parent / path)) as f:
            return json.load(f)
    except:
        return


def get_cf_location(loc: str):
    global loc_data
    loc = loc.upper()
    if loc_data is None:
        loc_data = read_loc_file('data/cf-colos.json')
    if loc_data is None:
        # From https://github.com/Netrvin/cloudflare-colo-list/blob/main/DC-Colos.json
        loc_data = read_loc_file('data/cf-colos.bundled.json')
    if loc_data is None:
        return
    data: dict = loc_data.get(loc)
    if not data:
        return
    return data.get('city')


def fill_cf_template_params(params: ErrorPageParams):
    # Get the real Ray ID / data center location from Cloudflare header
    ray_id_loc = request.headers.get('Cf-Ray')
    if ray_id_loc:
        params['ray_id'] = ray_id_loc[:16]

        cf_status = params.get('cloudflare_status')
        if cf_status is None:
            cf_status = params['cloudflare_status'] = {}
        if not cf_status.get('location'):
            loc = get_cf_location(ray_id_loc[-3:])
            if loc:
                cf_status['location'] = loc

    # Get the real client ip from remote_addr
    # If this server is behind proxies (e.g CF CDN / Nginx), make sure to set 'BEHIND_PROXY'=True in app config. Then ProxyFix will fix this variable
    # using X-Forwarded-For header from the proxy.
    params['client_ip'] = request.remote_addr


def sanitize_user_link(link: str):
    link = link.strip()
    link_lower = link
    if link_lower.startswith('http://') or link_lower.startswith('https://'):
        return link
    if '.' in link or '/' in link:
        return 'https://' + link
    return '#' + link


def sanitize_page_param_links(param: ErrorPageParams):
    more_info = param.get('more_information')
    if more_info:
        link = more_info.get('link')
        if link:
            more_info['link'] = sanitize_user_link(link)
    perf_sec_by = param.get('perf_sec_by')
    if perf_sec_by:
        link = perf_sec_by.get('link')
        if link:
            perf_sec_by['link'] = sanitize_user_link(link)


def render_extended_template(params: ErrorPageParams, *args: Any, **kwargs: Any) -> str:
    fill_cf_template_params(params)
    description = params.get('what_happened') or "There is an internal server error on Cloudflare's network."
    description = re.sub(r'<\/?.*?>', '', description).strip()

    status = 'ok'
    cf_status_obj = params.get('cloudflare_status')
    if cf_status_obj:
        cf_status = cf_status_obj.get('status')
        if cf_status == 'error':
            status = 'error'
    page_icon_url = current_app.config.get('PAGE_ICON_URL', '').replace('{status}', status)
    page_icon_type = current_app.config.get('PAGE_ICON_TYPE')
    page_image_url = current_app.config.get('PAGE_IMAGE_URL', '').replace('{status}', status)
    return render_cf_error_page(
        params=params,
        template=template,
        base=base_template,
        page_icon_url=page_icon_url,
        page_icon_type=page_icon_type,
        page_url=request.url,
        page_description=description,
        page_image_url=page_image_url,
        *args,
        **kwargs,
    )
