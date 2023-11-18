# -*- coding: utf-8 -*-
import json
import uuid
from datetime import datetime, date
from decimal import Decimal

from django.conf import settings
from xero_python.api_client import ApiClient, serialize
from xero_python.api_client.configuration import Configuration
from xero_python.api_client.oauth2 import OAuth2Token


class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        if isinstance(o, date):
            return o.isoformat()
        if isinstance(o, (uuid.UUID, Decimal)):
            return str(o)
        return super(JSONEncoder, self).default(o)


def parse_json(data):
    return json.loads(data, parse_float=Decimal)


def serialize_model(model):
    return jsonify(serialize(model))


def jsonify(data):
    return json.dumps(data, sort_keys=True, indent=4, cls=JSONEncoder)


def obtain_xero_oauth2_token(request):
    return request.session.get("token")


def store_xero_oauth2_token(request, token):
    request.session["token"] = token
    request.session.modified = True


def xero_api_client(request):
    return ApiClient(
        Configuration(
            debug=settings.DEBUG,
            oauth2_token=OAuth2Token(
                client_id=settings.CLIENT_ID, client_secret=settings.CLIENT_SECRET
            ),
        ),
        oauth2_token_getter=lambda: obtain_xero_oauth2_token(request),
        oauth2_token_saver=lambda token: store_xero_oauth2_token(request, token),
        pool_threads=1,
    )
