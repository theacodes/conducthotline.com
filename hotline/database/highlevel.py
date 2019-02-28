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

import peewee

from hotline.database import lowlevel


def list_events(user_id: str):
    query = (
        lowlevel.Event.select()
        .where(lowlevel.Event.owner_user_id == user_id)
        .order_by(lowlevel.Event.name)
    )
    yield from query


def new_event(user_id: str):
    event = lowlevel.Event()
    event.owner_user_id = user_id
    return event


def get_event(event_slug: str):
    return lowlevel.Event.get(lowlevel.Event.slug == event_slug)


def get_event_by_number(number: str):
    return lowlevel.Event.get(lowlevel.Event.primary_number == number)


def get_event_members(event):
    query = event.members
    yield from query


def get_verified_event_members(event):
    query = event.members.where(lowlevel.EventMember.verified == True)  # noqa
    yield from query


def new_event_member(event_slug: str):
    member = lowlevel.EventMember()
    member.event = get_event(event_slug)
    member.verified = False
    return member


def remove_event_member(event_slug: str, member_id):
    lowlevel.EventMember.get(
        lowlevel.EventMember.id == int(member_id)
    ).delete_instance()


def find_pending_member_by_number(member_number):
    try:
        return lowlevel.EventMember.get(
            lowlevel.EventMember.number == member_number,
            lowlevel.EventMember.verified == False,
        )  # noqa
    except peewee.DoesNotExist:
        return None


def find_unused_event_numbers():
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


def acquire_number(event_slug: str = None):
    with lowlevel.db.atomic():
        event = lowlevel.Event.get(lowlevel.Event.slug == event_slug)
        numbers = find_unused_event_numbers()

        # TODO: Check for no available numbers
        number = numbers[0]
        event.primary_number = number.number
        event.primary_number_id = number

        event.save()

        return event


def find_unused_relay_number(event_number, organizer_number):
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
