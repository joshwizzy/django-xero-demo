import json
from functools import wraps
from io import BytesIO

from django.conf import settings
from django.http import FileResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from requests_oauthlib import OAuth2Session
from xero_python.accounting import AccountingApi, Contact, ContactPerson, Contacts
from xero_python.api_client import serialize
from xero_python.exceptions import AccountingBadRequestException
from xero_python.identity import IdentityApi
from xero_python.utils import getvalue

from .utils import (
    jsonify,
    obtain_xero_oauth2_token,
    serialize_model,
    store_xero_oauth2_token,
    xero_api_client,
)


def xero_token_required(function):
    @wraps(function)
    def decorator(request, *args, **kwargs):
        xero_token = obtain_xero_oauth2_token(request)
        if not xero_token:
            return redirect(reverse("login"))

        return function(request, *args, **kwargs)

    return decorator


def index(request):
    xero_access = dict(obtain_xero_oauth2_token(request) or {})
    return render(
        request,
        "code.html",
        context={
            "title": "Home | oauth token",
            "code": json.dumps(xero_access, sort_keys=True, indent=4),
        },
    )


@xero_token_required
def tenants(request):
    api_client = xero_api_client(request)
    identity_api = IdentityApi(api_client)
    accounting_api = AccountingApi(api_client)

    available_tenants = []
    for connection in identity_api.get_connections():
        tenant = serialize(connection)
        if connection.tenant_type == "ORGANISATION":
            organisations = accounting_api.get_organisations(
                xero_tenant_id=connection.tenant_id
            )
            tenant["organisations"] = serialize(organisations)

        available_tenants.append(tenant)

    return render(
        request,
        "code.html",
        context={
            "title": "Xero Tenants",
            "code": json.dumps(available_tenants, sort_keys=True, indent=4),
        },
    )


@xero_token_required
def create_contact_person(request):
    xero_tenant_id = get_xero_tenant_id(request)
    api_client = xero_api_client(request)
    accounting_api = AccountingApi(api_client)

    contact_person = ContactPerson(
        first_name="John",
        last_name="Smith",
        email_address="john.smith@24locks.com",
        include_in_emails=True,
    )
    contact = Contact(
        name="FooBar",
        first_name="Foo",
        last_name="Bar",
        email_address="ben.bowden@24locks.com",
        contact_persons=[contact_person],
    )
    contacts = Contacts(contacts=[contact])
    try:
        created_contacts = accounting_api.create_contacts(
            xero_tenant_id, contacts=contacts
        )  # type: Contacts
    except AccountingBadRequestException as exception:
        sub_title = "Error: " + exception.reason
        code = jsonify(exception.error_data)
    else:
        sub_title = "Contact {} created.".format(
            getvalue(created_contacts, "contacts.0.name", "")
        )
        code = serialize_model(created_contacts)

    return render(
        request,
        "code.html",
        context={"title": "Create Contacts", "code": code, "sub_title": "sub_title"},
    )


@xero_token_required
def create_multiple_contacts(request):
    xero_tenant_id = get_xero_tenant_id(request)
    api_client = xero_api_client(request)
    accounting_api = AccountingApi(api_client)

    contact = Contact(
        name="George Jetson",
        first_name="George",
        last_name="Jetson",
        email_address="george.jetson@aol.com",
    )
    # Add the same contact twice - the first one will succeed, but the
    # second contact will fail with a validation error which we'll show.
    contacts = Contacts(contacts=[contact, contact])
    try:
        created_contacts = accounting_api.create_contacts(
            xero_tenant_id, contacts=contacts, summarize_errors=False
        )  # type: Contacts
    except AccountingBadRequestException as exception:
        sub_title = "Error: " + exception.reason
        result_list = None
        code = jsonify(exception.error_data)
    else:
        sub_title = ""
        result_list = []
        for contact in created_contacts.contacts:
            if contact.has_validation_errors:
                error = getvalue(contact.validation_errors, "0.message", "")
                result_list.append("Error: {}".format(error))
            else:
                result_list.append("Contact {} created.".format(contact.name))

        code = serialize_model(created_contacts)

    return render(
        request,
        "code.html",
        context={
            "title": "Create Multiple Contacts",
            "code": code,
            "result_list": result_list,
            "sub_title": sub_title,
        },
    )


@xero_token_required
def get_invoices(request):
    xero_tenant_id = get_xero_tenant_id(request)
    api_client = xero_api_client(request)
    accounting_api = AccountingApi(api_client)

    invoices = accounting_api.get_invoices(
        xero_tenant_id, statuses=["DRAFT", "SUBMITTED"]
    )
    code = serialize_model(invoices)
    sub_title = "Total invoices found: {}".format(len(invoices.invoices))

    return render(
        request,
        "code.html",
        context={"title": "Invoices", "code": code, "sub_title": sub_title},
    )


def login(request):
    xero = OAuth2Session(
        settings.CLIENT_ID,
        scope=settings.SCOPE,
        redirect_uri=settings.REDIRECT_URI,
        state=settings.STATE,
    )

    # Redirect user to GitHub for authorization
    authorization_url, state = xero.authorization_url(
        settings.AUTHORIZATION_URL, access_type="offline", prompt="select_account"
    )

    return redirect(authorization_url)


def oauth_callback(request):
    params = request.META["QUERY_STRING"]
    xero = OAuth2Session(
        settings.CLIENT_ID,
        scope=settings.SCOPE,
        redirect_uri=settings.REDIRECT_URI,
        state=settings.STATE,
    )

    try:
        token = xero.fetch_token(
            settings.ACCESS_TOKEN_URL,
            client_secret=settings.CLIENT_SECRET,
            authorization_response=f"{settings.REDIRECT_URI}/?{params}",
        )
    except Exception as e:
        print(e)
        raise
    # todo validate state value
    if token is None:
        return f"Access denied: response={params}"
    store_xero_oauth2_token(request, token)
    return redirect(reverse("index"))


def logout(request):
    store_xero_oauth2_token(request, None)
    return redirect(reverse("index"))


@xero_token_required
def export_token(request):
    token = obtain_xero_oauth2_token(request)
    buffer = BytesIO("token={!r}".format(token).encode("utf-8"))
    buffer.seek(0)
    response = FileResponse(
        buffer,
        as_attachment=True,
        filename="oauth2_token.py",
    )
    return response


@xero_token_required
def refresh_token(request):
    xero_token = obtain_xero_oauth2_token(request)
    api_client = xero_api_client(request)
    new_token = api_client.refresh_oauth2_token()
    return render(
        request,
        "code.html",
        context={
            "title": "Xero OAuth2 token",
            "code": jsonify({"Old Token": xero_token, "New token": new_token}),
            "sub_title": "token refreshed",
        },
    )


def get_xero_tenant_id(request):
    token = obtain_xero_oauth2_token(request)
    if not token:
        return None

    api_client = xero_api_client(request)
    identity_api = IdentityApi(api_client)
    for connection in identity_api.get_connections():
        if connection.tenant_type == "ORGANISATION":
            return connection.tenant_id
