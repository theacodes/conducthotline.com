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

import hotline.chatroom
import peewee
import playhouse.db_url
from hotline import audit_log, injector
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


def find_unused_event_numbers(country: str) -> List[models.Number]:
    return list(
        models.Number.select()
        .join(
            models.Event,
            peewee.JOIN.LEFT_OUTER,
            on=(models.Event.primary_number_id == models.Number.id),
        )
        .where(models.Event.primary_number_id.is_null())
        .where(models.Number.pool == models.NumberPool.EVENT)
        .where(models.Number.country == country)
        .limit(5)
    )


def acquire_number(event: models.Event) -> str:
    with models.db.atomic():
        numbers = find_unused_event_numbers(event.country)

        # TODO: Check for no available numbers
        number = numbers[0]
        event.primary_number = number.number
        event.primary_number_id = number

        event.save()

        return event.primary_number


def get_unused_relay_numbers_for_event(
    event: models.Event, organizer_numbers: List[str] = [], limit: int = 1
) -> List[str]:
    # TODO: Should probably be a join, but its unlikely this list will
    # get big enough in the near future to be an issue.

    # Find all relays currently being used by this event.
    used_relay_numbers_query = models.SmsChat.select(models.SmsChat.relay_number).where(
        models.SmsChat.event == event
    )

    used_relay_numbers = [row.relay_number for row in used_relay_numbers_query]

    # Further refine - don't include relays if they're already assigned to the same organizer
    # in another event.
    # Aside: this query might actually be enough to determine all used relays.
    event_organizers_used_relays_query = models.SmsChatConnection.select(
        models.SmsChatConnection.relay_number
    ).where(models.SmsChatConnection.user_number.in_(organizer_numbers))

    event_organizers_used_relays = [
        row.relay_number for row in event_organizers_used_relays_query
    ]

    # Combine those together into a set.
    used_relay_numbers = list(set(used_relay_numbers + event_organizers_used_relays))

    # Now find numbers in the SMS RELAY pool that aren't in that set.
    unused_number_query = (
        models.Number.select(models.Number.number)
        .where(models.Number.pool == models.NumberPool.SMS_RELAY)
        .where(models.Number.country == event.country)
        .where(models.Number.number.not_in(used_relay_numbers))
        .limit(limit)
    )

    numbers = [row.number for row in unused_number_query]

    return numbers


def get_remaining_relays_for_event(event: models.Event) -> int:
    return len(get_unused_relay_numbers_for_event(event, limit=1000))


def find_unused_relay_number(
    event: models.Event, organizer_numbers: List[str]
) -> Optional[str]:
    """Find a relay number that isn't currently used by the event"""
    numbers = get_unused_relay_numbers_for_event(
        event, organizer_numbers=organizer_numbers
    )
    if not numbers:
        return None
    else:
        return numbers[0]


def save_room(
    room: hotline.chatroom.Chatroom, relay_number: str, event: models.Event
) -> None:
    with models.db.atomic():
        smschat = models.SmsChat.create(
            event=event, room=room, relay_number=relay_number
        )

        # Create connections so that the sms chat can be looked up by user number
        # and relay number.
        for connection in room.users:
            models.SmsChatConnection.create(
                user_number=connection.number,
                relay_number=connection.relay,
                user_name=connection.name,
                smschat=smschat,
            )


def find_smschat_by_user_and_relay_numbers(
    user_number: str, relay_number: str
) -> Optional[models.SmsChat]:
    try:
        connection = models.SmsChatConnection.get(
            models.SmsChatConnection.user_number == user_number,
            models.SmsChatConnection.relay_number == relay_number,
        )
        return connection.smschat

    except peewee.DoesNotExist:
        return None


def remove_event_chat(event: models.Event, chat_id: str, user: dict):
    item = models.SmsChat.get(
        models.SmsChat.event == event, models.SmsChat.id == int(chat_id)
    )

    item.delete_instance()

    # Delete all connections
    models.SmsChatConnection.delete().where(
        models.SmsChatConnection.smschat == item
    ).execute()

    audit_log.log(
        kind=audit_log.Kind.CHAT_DELETED,
        description=f"{user['name']} deleted the chat with the relay number {item.relay_number}.",
        event=event,
        user=user["user_id"],
    )


def get_chats_for_event(event: models.Event):
    return (
        models.SmsChat.select()
        .where(models.SmsChat.event == event)
        .order_by(-models.SmsChat.timestamp)
    )


def get_logs_for_event(event: models.Event):
    return (
        models.AuditLog.select()
        .where(models.AuditLog.event == event)
        .order_by(-models.AuditLog.timestamp)
    )


def get_blocklist_for_event(event: models.Event):
    return (
        models.BlockList.select()
        .where(models.BlockList.event == event)
        .order_by(-models.BlockList.timestamp)
    )


def create_blocklist_item(event: models.Event, log_id: str, user: dict):
    log = models.AuditLog.get(
        models.AuditLog.event == event, models.AuditLog.id == int(log_id)
    )

    models.BlockList.create(
        event=event, number=log.reporter_number, blocked_by=user["name"]
    )

    audit_log.log(
        kind=audit_log.Kind.NUMBER_BLOCKED,
        description=f"{user['name']} blocked the number ending in {log.reporter_number[-4:]}.",
        event=event,
        user=user["user_id"],
    )


def remove_blocklist_item(event: models.Event, blocklist_id: str, user: dict):
    item = models.BlockList.get(
        models.BlockList.event == event, models.BlockList.id == int(blocklist_id)
    )

    item.delete_instance()

    audit_log.log(
        kind=audit_log.Kind.NUMBER_UNBLOCKED,
        description=f"{user['name']} unblocked the number ending in {item.number[-4:]}.",
        event=event,
        user=user["user_id"],
    )


def check_if_blocked(event: models.Event, number: str):
    try:
        models.BlockList.get(
            models.BlockList.event == event, models.BlockList.number == number
        )
        return True
    except peewee.DoesNotExist:
        return False
