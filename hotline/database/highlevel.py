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


def list_events(user_id: str) -> Iterable[models.Event]:
    query = (
        models.Event.select()
        .where(models.Event.owner_user_id == user_id)
        .order_by(models.Event.name)
    )
    yield from query


def new_event(user_id: str) -> models.Event:
    event = models.Event()
    event.owner_user_id = user_id
    return event


def get_event(event_slug: str) -> models.Event:
    return models.Event.get(models.Event.slug == event_slug)


def get_event_by_number(number: str) -> Optional[models.Event]:
    try:
        return models.Event.get(models.Event.primary_number == number)
    except peewee.DoesNotExist:
        return None


def get_event_members(event) -> Iterable[models.EventMember]:
    query = event.members
    yield from query


def get_verified_event_members(event) -> Iterable[models.EventMember]:
    query = event.members.where(models.EventMember.verified == True)  # noqa
    yield from query


def new_event_member(event_slug: str) -> models.EventMember:
    member = models.EventMember()
    member.event = get_event(event_slug)
    member.verified = False
    return member


def remove_event_member(event_slug: str, member_id: str) -> None:
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


def acquire_number(event_slug: str = None) -> str:
    with models.db.atomic():
        event = models.Event.get(models.Event.slug == event_slug)
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

    print("Used relay numbers: ", used_relay_numbers)

    # Don't use the event number as a relay number
    used_relay_numbers.append(event_number)

    unused_number_query = (
        models.Number.select(models.Number.number)
        .where(models.Number.number.not_in(used_relay_numbers))
        .limit(1)
    )

    numbers = [row.number for row in unused_number_query]

    print("Available relay numbers: ", numbers)

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
