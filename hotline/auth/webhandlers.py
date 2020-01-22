# Copyright 2019 Alethea Katherine Flowers
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import functools

import firebase_admin
import firebase_admin.auth
import firebase_admin.credentials
import flask
from hotline import injector

_COOKIE_NAME = "auth-session"

blueprint = flask.Blueprint("auth", __name__, template_folder="templates")


@injector.needs("secrets.firebase")
def _is_development_auth(firebase):
    if firebase.get("development_mode", False):
        return True
    return False


@injector.provides(needs=["secrets.firebase.service_account"])
def firebase_admin_app(service_account):
    try:
        return firebase_admin.get_app()
    except ValueError:
        pass
    return firebase_admin.initialize_app(
        firebase_admin.credentials.Certificate(service_account)
    )


def auth_required(f):
    @functools.wraps(f)
    def auth_required_view(*args, **kwargs):
        if _is_development_auth():
            flask.g.user = {
                "user_id": "dev",
                "name": "Developer",
                "email": "developer@conducthotline.com",
                "picture": None,
                "super_admin": True,
            }
            return f(*args, **kwargs)

        firebase_admin_app = injector.get("firebase_admin_app")
        session_cookie = flask.request.cookies.get(_COOKIE_NAME)

        try:
            decoded_claims = firebase_admin.auth.verify_session_cookie(
                session_cookie, check_revoked=True, app=firebase_admin_app
            )
        except ValueError as exc:
            # Session cookie is unavailable or invalid. Force user to login.
            return flask.redirect(flask.url_for("auth.login", next=flask.request.path))
        except firebase_admin.auth.AuthError as exc:
            # Session revoked. Force user to login.
            return flask.redirect(flask.url_for("auth.login", next=flask.request.path))

        flask.g.user = decoded_claims
        flask.g.user.setdefault("name", flask.g.user.get("email", "Unknown"))
        super_admins = injector.get("secrets.super_admins")
        flask.g.user["super_admin"] = flask.g.user["user_id"] in super_admins
        return f(*args, **kwargs)

    return auth_required_view


def super_admin_required(f):
    @functools.wraps(f)
    @auth_required
    def super_admin_required_view(*args, **kwargs):
        if not flask.g.user.get("super_admin"):
            flask.abort(403)

        return f(*args, **kwargs)

    return super_admin_required_view


@blueprint.route("/auth/login")
def login():
    return flask.render_template("login.html", next=flask.request.args.get("next"))


@blueprint.route("/auth/config.json")
@injector.needs("secrets.firebase.config")
def config(config):
    return flask.jsonify(config)


@blueprint.route("/auth/token-login", methods=["POST"])
@injector.needs("firebase_admin_app")
def token_login(firebase_admin_app):
    id_token = flask.request.headers["Authentication"].split(" ")[1]

    # Set session expiration to 5 days.
    expires_in = datetime.timedelta(days=5)
    try:
        # Create the session cookie. This will also verify the ID token in the process.
        # The session cookie will have the same claims as the ID token.
        session_cookie = firebase_admin.auth.create_session_cookie(
            id_token, expires_in=expires_in, app=firebase_admin_app
        )
        response = flask.Response(status="204")

        expires = datetime.datetime.now() + expires_in
        # TODO: Set secure to True. (or use Talisman)
        response.set_cookie(
            _COOKIE_NAME, session_cookie, expires=expires, httponly=True, secure=False
        )
        return response
    except firebase_admin.auth.AuthError:
        return 401, "Failed to create a session cookie"

    return "OK"


@blueprint.route("/auth/logout")
@injector.needs("firebase_admin_app")
def logout(firebase_admin_app):
    session_cookie = flask.request.cookies.get(_COOKIE_NAME)

    response = flask.make_response(flask.redirect(flask.url_for("auth.login")))
    response.set_cookie(_COOKIE_NAME, expires=0)

    try:
        decoded_claims = firebase_admin.auth.verify_session_cookie(
            session_cookie, app=firebase_admin_app
        )
        firebase_admin.auth.revoke_refresh_tokens(
            decoded_claims["sub"], app=firebase_admin_app
        )
    except ValueError:
        # The token was invalid for one reason or another. Doesn't matter,
        # just clear the session and redirect.
        pass

    return response


@blueprint.route("/auth/info")
@auth_required
def info():
    user = flask.g.user
    print(flask.g.user)
    return f"{user['name']} ({user['user_id']})"
