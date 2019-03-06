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

import functools

import flask

import hotline.database.ext
import hotline.telephony.verification
from hotline import audit_log
from hotline.auth import auth_required
from hotline.database import highlevel as db
from hotline.events import forms

blueprint = flask.Blueprint("events", __name__, template_folder="templates")
hotline.database.ext.init_app(blueprint)


def event_access_required(view):
    @functools.wraps(view)
    @auth_required
    def check_access_decorator(event_slug, *args, **kwargs):
        event = db.check_if_user_is_organizer(event_slug, flask.g.user["user_id"])

        if event is None:
            flask.abort(404)

        kwargs["event"] = event
        kwargs["user"] = flask.g.user
        return view(*args, **kwargs)

    return check_access_decorator


@blueprint.route("/e/<event_slug>")
def info(event_slug):
    event = db.get_event_by_slug(event_slug)

    if event is None:
        flask.abort(404)

    return flask.render_template("info.html", event=event)


@blueprint.route("/events")
@auth_required
def list():
    user_id = flask.g.user["user_id"]
    events = db.list_events_for_user(user_id=user_id)
    return flask.render_template("list.html", events=events)


@blueprint.route("/events/add", methods=["GET", "POST"])
@auth_required
def add():
    user = flask.g.user
    form = forms.EventEditForm(flask.request.form)

    if flask.request.method == "POST" and form.validate():
        event = db.new_event()
        form.populate_obj(event)
        event.save()
        db.add_event_organizer(event, user)

        audit_log.log(
            audit_log.Kind.EVENT_MODIFIED,
            description=f"{flask.g.user['name']} created the event.",
            event=event,
            user=user["user_id"],
        )

        return flask.redirect(flask.url_for(".numbers", event_slug=event.slug))

    return flask.render_template("add.html", form=form)


@blueprint.route("/events/<event_slug>/details", methods=["GET", "POST"])
@event_access_required
def details(event, user):
    form = forms.EventEditForm(flask.request.form, event)

    if flask.request.method == "POST" and form.validate():
        form.populate_obj(event)
        event.save()

        audit_log.log(
            audit_log.Kind.EVENT_MODIFIED,
            description=f"{flask.g.user['name']} updated the event details.",
            event=event,
            user=user["user_id"],
        )

        return flask.redirect(
            flask.url_for(flask.request.endpoint, event_slug=event.slug)
        )

    return flask.render_template("edit.html", event=event, form=form)


@blueprint.route("/events/<event_slug>/numbers", methods=["GET", "POST"])
@event_access_required
def numbers(event, user):
    members = db.get_event_members(event)
    form = forms.AddMemberForm(flask.request.form)

    if flask.request.method == "POST" and form.validate():
        member = db.new_event_member(event)
        form.populate_obj(member)
        member.save()

        audit_log.log(
            audit_log.Kind.MEMBER_ADDED,
            description=f"{flask.g.user['name']} added {member.name}.",
            event=event,
            user=user["user_id"],
        )

        # Start the verification process.
        hotline.telephony.verification.start_member_verification(member)

        return flask.redirect(
            flask.url_for(flask.request.endpoint, event_slug=event.slug)
        )

    return flask.render_template(
        "numbers.html", event=event, members=members, form=form
    )


@blueprint.route("/events/<event_slug>/members/remove/<member_id>")
@event_access_required
def remove_member(member_id, event, user):
    member = db.get_member(member_id)

    db.remove_event_member(member_id)

    audit_log.log(
        audit_log.Kind.MEMBER_REMOVED,
        description=f"{flask.g.user['name']} removed {member.name}.",
        event=event,
        user=user["user_id"],
    )

    return flask.redirect(flask.url_for(".numbers", event_slug=event.slug))


@blueprint.route("/events/<event_slug>/organizers", methods=["GET", "POST"])
@event_access_required
def organizers(event, user):
    organizers = db.get_event_organizers(event)

    form = forms.AddOrganizerForm(flask.request.form)

    if flask.request.method == "POST" and form.validate():
        db.add_pending_event_organizer(event, form.email.data)

        audit_log.log(
            audit_log.Kind.ORGANIZER_ADDED,
            description=f"{flask.g.user['name']} invited {form.email.data}.",
            event=event,
            user=user["user_id"],
        )

        return flask.redirect(
            flask.url_for(flask.request.endpoint, event_slug=event.slug)
        )

    return flask.render_template(
        "organizers.html", event=event, organizers=organizers, form=form
    )


@blueprint.route("/events/<event_slug>/organizers/remove/<organizer_id>")
@event_access_required
def remove_organizer(organizer_id, event, user):
    organizer = db.get_event_organizer(organizer_id)

    db.remove_event_organizer(organizer_id)

    audit_log.log(
        audit_log.Kind.ORGANIZER_REMOVED,
        description=f"{flask.g.user['name']} removed {organizer.user_email}.",
        event=event,
        user=user["user_id"],
    )

    return flask.redirect(flask.url_for(".organizers", event_slug=event.slug))


@blueprint.route("/events/organizers/invitations/<invitation_id>")
@auth_required
def accept_organizer_invitation(invitation_id):
    event = db.accept_organizer_invitation(invitation_id, flask.g.user)

    if event is None:
        flask.abort(403)

    return flask.redirect(flask.url_for(".details", event_slug=event.slug))


@blueprint.route("/events/<event_slug>/release")
@event_access_required
def release(event, user):
    previous_number = event.primary_number
    event.primary_number = None
    event.primary_number_id = None
    event.save()

    audit_log.log(
        audit_log.Kind.NUMBER_RELEASED,
        description=f"{flask.g.user['name']} released the number {previous_number}",
        event=event,
        user=user["user_id"],
    )

    return flask.redirect(flask.url_for(".numbers", event_slug=event.slug))


@blueprint.route("/events/<event_slug>/acquire")
@event_access_required
def acquire(event, user):
    new_number = db.acquire_number(event)

    audit_log.log(
        audit_log.Kind.NUMBER_ACQUIRED,
        description=f"{flask.g.user['name']} acquired the number {new_number}",
        event=event,
        user=user["user_id"],
    )

    return flask.redirect(flask.url_for(".numbers", event_slug=event.slug))


@blueprint.route("/events/<event_slug>/logs")
@event_access_required
def logs(event, user):
    logs = db.get_logs_for_event(event)

    return flask.render_template(
        "logs.html", event=event, logs=logs, Kind=audit_log.Kind
    )
