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

"""High-level database operations."""

from typing import Iterable, List, Optional

import peewee
import playhouse.db_url

import hotline.chatroom
from hotline import injector
from hotline.database import models


@injector.needs("secrets.database")
def initialize_db(database):
    models.db.initialize(playhouse.db_url.connect(database))


def list_events_for_user(user_id: str) -> Iterable[models.Event]:
    query = (
        models.Event.select(models.Event.name, models.Event.slug)
        .join(models.EventOrganizer)
        .where(models.EventOrganizer.user_id == user_id)
        .order_by(models.Event.name)
    )

    yield from query


def check_if_user_is_organizer(event_slug, user_id) -> Optional[models.Event]:
    query = (
        models.Event.select()
        .join(models.EventOrganizer)
        .where(models.Event.slug == event_slug)
        .where(models.EventOrganizer.user_id == user_id)
        .order_by(models.Event.name)
    )
    try:
        return query.get()
    except peewee.DoesNotExist:
        return None


def new_event() -> models.Event:
    event = models.Event()
    return event


def get_event_by_slug(event_slug: str) -> Optional[models.Event]:
    try:
        return models.Event.get(models.Event.slug == event_slug)
    except peewee.DoesNotExist:
        return None


def get_event_by_number(number: str) -> Optional[models.Event]:
    try:
        return models.Event.get(models.Event.primary_number == number)
    except peewee.DoesNotExist:
        return None


def get_event_organizers(event: models.Event):
    query = event.organizers
    yield from query


def add_event_organizer(event: models.Event, user: dict) -> None:
    organizer_entry = models.EventOrganizer()
    organizer_entry.event = event
    organizer_entry.user_id = user["user_id"]
    organizer_entry.user_name = user["name"]
    organizer_entry.user_email = user["email"]
    organizer_entry.save()


def add_pending_event_organizer(event: models.Event, user_email: str) -> None:
    organizer_entry = models.EventOrganizer()
    organizer_entry.event = event
    organizer_entry.user_email = user_email
    organizer_entry.save()


def accept_organizer_invitation(
    invitation_id: str, user: dict
) -> Optional[models.Event]:
    try:
        organizer_entry = get_event_organizer(invitation_id)
    except peewee.DoesNotExist:
        return None

    if organizer_entry.user_email != user["email"]:
        return None

    organizer_entry.user_id = user["user_id"]
    organizer_entry.user_name = user["name"]
    organizer_entry.save()

    return organizer_entry.event


def remove_event_organizer(organizer_id: str) -> None:
    models.EventOrganizer.get(
        models.EventOrganizer.id == int(organizer_id)
    ).delete_instance()


def get_event_organizer(organizer_id: str) -> models.EventOrganizer:
    return models.EventOrganizer.get_by_id(organizer_id)


def get_event_members(event) -> Iterable[models.EventMember]:
    query = event.members
    yield from query


def get_verified_event_members(event) -> Iterable[models.EventMember]:
    query = event.members.where(models.EventMember.verified == True)  # noqa
    yield from query


def new_event_member(event: models.Event) -> models.EventMember:
    member = models.EventMember()
    member.event = event
    member.verified = False
    return member


def remove_event_member(member_id: str) -> None:
    models.EventMember.get(models.EventMember.id == int(member_id)).delete_instance()


def get_member(member_id: str) -> models.EventMember:
    return models.EventMember.get_by_id(member_id)


def get_member_by_number(member_number) -> Optional[models.EventMember]:
    try:
        return models.EventMember.get(models.EventMember.number == member_number)
    except peewee.DoesNotExist:
        return None


def find_pending_member_by_number(member_number) -> Optional[models.EventMember]:
    try:
        return models.EventMember.get(
            models.EventMember.number == member_number,
            models.EventMember.verified == False,
        )  # noqa
    except peewee.DoesNotExist:
        return None


def find_unused_event_numbers() -> List[models.Number]:
    return list(
        models.Number.select()
        .join(
            models.Event,
            peewee.JOIN.LEFT_OUTER,
            on=(models.Event.primary_number_id == models.Number.id),
        )
        .where(models.Event.primary_number_id.is_null())
        .limit(5)
    )


def acquire_number(event: models.Event) -> str:
    with models.db.atomic():
        numbers = find_unused_event_numbers()

        # TODO: Check for no available numbers
        number = numbers[0]
        event.primary_number = number.number
        event.primary_number_id = number

        event.save()

        return event.primary_number


def find_unused_relay_number(event_number, organizer_number) -> Optional[str]:
    """Find a relay number that isn't currently used by an existing chatroom
    connection."""
    # TODO: Should probably be a join, but its unlikely this list will
    # get big enough in the near future to be an issue.
    used_relay_numbers_query = models.ChatroomConnection.select(
        models.ChatroomConnection.relay_number
    ).where(models.ChatroomConnection.user_number == organizer_number)

    used_relay_numbers = [row.relay_number for row in used_relay_numbers_query]

    # Don't use the event number as a relay number
    used_relay_numbers.append(event_number)

    unused_number_query = (
        models.Number.select(models.Number.number)
        .where(models.Number.number.not_in(used_relay_numbers))
        .limit(1)
    )

    numbers = [row.number for row in unused_number_query]

    if not numbers:
        return None
    else:
        return numbers[0]


def save_room(room: hotline.chatroom.Chatroom, event: models.Event) -> None:
    with models.db.atomic():
        room_row = models.Chatroom.create(event=event, room=room)

        for connection in room.users:
            models.ChatroomConnection.create(
                user_number=connection.number,
                relay_number=connection.relay,
                user_name=connection.name,
                chatroom=room_row,
            )


def find_room_by_user_and_relay_numbers(
    user_number: str, relay_number: str
) -> Optional[hotline.chatroom.Chatroom]:
    try:
        connection = models.ChatroomConnection.get(
            models.ChatroomConnection.user_number == user_number,
            models.ChatroomConnection.relay_number == relay_number,
        )

        # This could be faster with a join, but I'm not terribly worried about speed right now.
        return connection.chatroom.room

    except peewee.DoesNotExist:
        return None


def get_logs_for_event(event: models.Event):
    return (
        models.AuditLog.select()
        .where(models.AuditLog.event == event)
        .order_by(-models.AuditLog.timestamp)
    )
