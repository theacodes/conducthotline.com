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

import hotline.chatroom
from hotline.database import lowlevel


def list_events(user_id: str) -> Iterable[lowlevel.Event]:
    query = (
        lowlevel.Event.select()
        .where(lowlevel.Event.owner_user_id == user_id)
        .order_by(lowlevel.Event.name)
    )
    yield from query


def new_event(user_id: str) -> lowlevel.Event:
    event = lowlevel.Event()
    event.owner_user_id = user_id
    return event


def get_event(event_slug: str) -> lowlevel.Event:
    return lowlevel.Event.get(lowlevel.Event.slug == event_slug)


def get_event_by_number(number: str) -> Optional[lowlevel.Event]:
    try:
        return lowlevel.Event.get(lowlevel.Event.primary_number == number)
    except peewee.DoesNotExist:
        return None


def get_event_members(event) -> Iterable[lowlevel.EventMember]:
    query = event.members
    yield from query


def get_verified_event_members(event) -> Iterable[lowlevel.EventMember]:
    query = event.members.where(lowlevel.EventMember.verified == True)  # noqa
    yield from query


def new_event_member(event_slug: str) -> lowlevel.EventMember:
    member = lowlevel.EventMember()
    member.event = get_event(event_slug)
    member.verified = False
    return member


def remove_event_member(event_slug: str, member_id: str) -> None:
    lowlevel.EventMember.get(
        lowlevel.EventMember.id == int(member_id)
    ).delete_instance()


def get_member_by_number(member_number) -> Optional[lowlevel.EventMember]:
    try:
        return lowlevel.EventMember.get(lowlevel.EventMember.number == member_number)
    except peewee.DoesNotExist:
        return None


def find_pending_member_by_number(member_number) -> Optional[lowlevel.EventMember]:
    try:
        return lowlevel.EventMember.get(
            lowlevel.EventMember.number == member_number,
            lowlevel.EventMember.verified == False,
        )  # noqa
    except peewee.DoesNotExist:
        return None


def find_unused_event_numbers() -> List[lowlevel.Number]:
    return list(
        lowlevel.Number.select()
        .join(
            lowlevel.Event,
            peewee.JOIN.LEFT_OUTER,
            on=(lowlevel.Event.primary_number_id == lowlevel.Number.id),
        )
        .where(lowlevel.Event.primary_number_id.is_null())
        .limit(5)
    )


def acquire_number(event_slug: str = None) -> lowlevel.Event:
    with lowlevel.db.atomic():
        event = lowlevel.Event.get(lowlevel.Event.slug == event_slug)
        numbers = find_unused_event_numbers()

        # TODO: Check for no available numbers
        number = numbers[0]
        event.primary_number = number.number
        event.primary_number_id = number

        event.save()

        return event


def find_unused_relay_number(event_number, organizer_number) -> Optional[str]:
    """Find a relay number that isn't currently used by an existing chatroom
    connection."""
    # TODO: Should probably be a join, but its unlikely this list will
    # get big enough in the near future to be an issue.
    used_relay_numbers_query = lowlevel.ChatroomConnection.select(
        lowlevel.ChatroomConnection.relay_number
    ).where(lowlevel.ChatroomConnection.user_number == organizer_number)

    used_relay_numbers = [row.relay_number for row in used_relay_numbers_query]

    print("Used relay numbers: ", used_relay_numbers)

    # Don't use the event number as a relay number
    used_relay_numbers.append(event_number)

    unused_number_query = (
        lowlevel.Number.select(lowlevel.Number.number)
        .where(lowlevel.Number.number.not_in(used_relay_numbers))
        .limit(1)
    )

    numbers = [row.number for row in unused_number_query]

    print("Available relay numbers: ", numbers)

    if not numbers:
        return None
    else:
        return numbers[0]


def save_room(room: hotline.chatroom.Chatroom, event: lowlevel.Event) -> None:
    with lowlevel.db.atomic():
        room_row = lowlevel.Chatroom.create(event=event, room=room)

        for connection in room.users:
            lowlevel.ChatroomConnection.create(
                user_number=connection.number,
                relay_number=connection.relay,
                user_name=connection.name,
                chatroom=room_row,
            )


def find_room_by_user_and_relay_numbers(
    user_number: str, relay_number: str
) -> Optional[hotline.chatroom.Chatroom]:
    try:
        connection = lowlevel.ChatroomConnection.get(
            lowlevel.ChatroomConnection.user_number == user_number,
            lowlevel.ChatroomConnection.relay_number == relay_number,
        )

        # This could be faster with a join, but I'm not terribly worried about speed right now.
        return connection.chatroom.room

    except peewee.DoesNotExist:
        return None
