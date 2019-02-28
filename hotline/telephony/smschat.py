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

"""Implements an SMS-based chatroom.

This uses the database as well as the abstract chatroom to build an SMS-based
chat room. This is further tailored specifically to the conduct hotline by
initiating a *new* chatroom when a reporter messages an event's number.
"""

from typing import Optional

import peewee

import hotline.chatroom
from hotline.database import highlevel as db
from hotline.database import lowlevel as models


class SmsChatError(Exception):
    pass


class EventDoesNotExist(SmsChatError):
    pass


class NoOrganizersAvailable(SmsChatError):
    pass


class NoRelaysAvailable(SmsChatError):
    pass


def _create_room(event_number: str, reporter_number: str) -> hotline.chatroom.Chatroom:
    """Creates a room for the event with the given primary number.

    The alogrithm is a little tricky here. The event organizers can not use
    the primary number as the chat relay for this chat, so a new number must be
    used.
    """
    # Find the event.
    event = db.get_event_by_number(event_number)

    if not event:
        raise EventDoesNotExist(f"No event for number {event_number}.")

    # Create a chatroom
    chatroom = hotline.chatroom.Chatroom()
    chatroom.add_user(name="Reporter", number=reporter_number, relay=event_number)

    # Find all organizers.
    organizers = list(db.get_verified_event_members(event))

    if not organizers:
        raise NoOrganizersAvailable(f"No organizers found for {event.name}. :/")

    # Find an unused number to use for the organizers' relay.
    # Use the first organizer's number here, as all organizers should be
    # assigned the same relay anyway.
    organizer_number = organizers[0].number
    relay_number = db.find_unused_relay_number(event.primary_number, organizer_number)

    print("Relay number: ", relay_number)

    if not relay_number:
        raise NoRelaysAvailable()

    # Now add the organizers and their relay.
    for organizer in organizers:
        chatroom.add_user(
            name=organizer.name, number=organizer.number, relay=relay_number
        )

    # Save the chatroom.
    db.save_room(chatroom, event=event)
    return chatroom


def _find_room(user_number: str, relay_number: str) -> hotline.chatroom.Chatroom:
    with models.db.atomic():
        # Try to find an existing room first.
        room = db.find_room_by_user_and_relay_numbers(user_number, relay_number)

        if room is not None:
            return room

        # Create a new room.
        return _create_room(relay_number, user_number)


def handle_message(sender: str, relay: str, message: str):
    """Handles an incoming SMS and hands it off to the appropriate room."""

    room = _find_room(user_number=sender, relay_number=relay)

    room.relay(sender, message, hotline.telephony.lowlevel.send_sms)
