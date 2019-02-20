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

from typing import Optional

import peewee

import hotline.telephony.chatroom
from hotline.database import lowlevel


def list_events(user_id: str = None):
    with lowlevel.db:
        query = lowlevel.Event.select().order_by(lowlevel.Event.name)
        # TODO: User query.
        yield from query


def get_event(event_slug: str = None):
    with lowlevel.db:
        return lowlevel.Event.get(lowlevel.Event.slug == event_slug)


def acquire_number(event_slug: str = None):
    with lowlevel.db.atomic():
        event = lowlevel.Event.get(lowlevel.Event.slug == event_slug)
        numbers = lowlevel.find_unused_event_numbers()

        # TODO: Check for no available numbers
        number = numbers[0]
        event.primary_number = number.number
        event.primary_number_id = number

        event.save()

        return event


def _save_room(room: hotline.telephony.chatroom.Chatroom, event: lowlevel.Event):
    with lowlevel.db.atomic():
        room_row = lowlevel.Chatroom.create(event=event, room=room)

        for connection in room.users:
            lowlevel.ChatroomConnection.create(
                user_number=connection.number,
                relay_number=connection.relay,
                user_name=connection.name,
                chatroom=room_row,
            )


def create_room(
    event_number: str, reporter_number: str
) -> hotline.telephony.chatroom.Chatroom:
    """Creates a room for the event with the given primary number.

    The alogrithm is a little tricky here. The event organizers can not use
    the primary number as the chat relay for this chat, so a new number must be
    used.
    """
    # Find the event.
    event = lowlevel.Event.get(lowlevel.Event.primary_number == event_number)

    # Create a chatroom
    chatroom = hotline.telephony.chatroom.Chatroom()
    chatroom.add_user(
        name="Reporter", user_number=reporter_number, relay_number=event_number
    )

    # Find all organizers.
    # TODO
    organizers = [("Thea", "16785888466")]

    # Find an unused number to use for the organizers' relay.
    # Use the first organizer's number here, as all organizers should be
    # assigned the same relay anyway.
    organizer_number = organizers[0][1]
    relay_number = lowlevel.find_unused_relay_number(
        event.primary_number, organizer_number
    )

    print("Relay number", relay_number)

    # Now add the organizers and their relay.
    for organizer in organizers:
        chatroom.add_user(
            name=organizer[0], user_number=organizer[1], relay_number=relay_number
        )

    print(chatroom.serialize())

    # Save the chatroom.
    return _save_room(chatroom, event=event)


def find_room_for_user(
    user_number: str, relay_number: str
) -> Optional[hotline.telephony.chatroom.Chatroom]:
    with lowlevel.db:
        try:
            connection = lowlevel.ChatroomConnection.get(
                lowlevel.ChatroomConnection.user_number == user_number,
                lowlevel.ChatroomConnection.relay_number == relay_number,
            )

            # This could be faster with a join, but I'm not terribly worried about speed right now.
            return connection.chatroom.room

        except peewee.DoesNotExist:
            return None
