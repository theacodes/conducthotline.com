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

import logging

import hotline.chatroom
from hotline import audit_log, common_text
from hotline.database import highlevel as db
from hotline.database import models
from hotline.telephony import lowlevel
import nexmo


class SmsChatError(Exception):
    pass


class EventDoesNotExist(SmsChatError):
    pass


class NumberBlocked(SmsChatError):
    pass


class NoOrganizersAvailable(SmsChatError):
    pass


class NoRelaysAvailable(SmsChatError):
    pass


def _create_room(event_number: str, reporter_number: str) -> hotline.chatroom.Chatroom:
    """Creates a room for the event with the given primary number.

    The algorithm is a little tricky here. The event organizers can not use
    the primary number as the chat relay for this chat, so a new number must be
    used.
    """
    # Find the event.
    event = db.get_event_by_number(event_number)

    if not event:
        raise EventDoesNotExist()

    # Make sure the number isn't blocked.
    if db.check_if_blocked(event=event, number=reporter_number):
        raise NumberBlocked()

    # Create a chatroom
    chatroom = hotline.chatroom.Chatroom()
    chatroom.add_user(name="Reporter", number=reporter_number, relay=event_number)

    # Find all organizers.
    organizers = list(db.get_verified_event_members(event))

    if not organizers:
        raise NoOrganizersAvailable()

    # Find an unused number to use for the organizers' relay.
    organizer_numbers = [organizer.number for organizer in organizers]
    relay_number = db.find_unused_relay_number(
        event, organizer_numbers=organizer_numbers
    )

    if not relay_number:
        raise NoRelaysAvailable()

    # Now add the organizers and their relay.
    for organizer in organizers:
        chatroom.add_user(
            name=organizer.name, number=organizer.number, relay=relay_number
        )

    # Save the chatroom.
    db.save_room(chatroom, relay_number=relay_number, event=event)

    audit_log.log(
        audit_log.Kind.SMS_CONVERSATION_STARTED,
        description=f"A new sms conversation was started. Last 4 digits of number is {reporter_number[-4:]}",
        event=event,
        reporter_number=reporter_number,
    )

    # Determine the greeting.
    if event.sms_greeting is not None and event.sms_greeting.strip():
        greeting = event.sms_greeting
    else:
        greeting = common_text.sms_default_greeting.format(event=event)

    # Send welcome messages.
    lowlevel.send_sms(sender=event_number, to=reporter_number, message=greeting)

    # Send instructions for how to opt-out by replying with STOP.
    lowlevel.send_sms(
        sender=event_number, to=reporter_number, message=common_text.sms_opt_out
    )

    for organizer in organizers:
        lowlevel.send_sms(
            sender=relay_number,
            to=organizer.number,
            message=common_text.sms_introduction.format(
                event=event, reporter_number=reporter_number[-4:]
            ),
        )

    return chatroom


def _send_sms_no_fail(*args, **kwargs):
    """Sends an SMS but does not raise an exception if an error occurs,
    instead, it just logs the exception."""
    try:
        hotline.telephony.lowlevel.send_sms(*args, **kwargs)
    except nexmo.ClientError:
        logging.exception("Failed to send message for SMS relay.")


def maybe_handle_stop(
    sender: str, relay: str, message: str, smschat: models.SmsChat
) -> bool:
    """Handle a potential stop request for a given number and SmsChat."""
    if message.strip().lower() != "stop":
        return False

    # Notify other chatroom members.
    room = smschat.room
    room.relay(sender, common_text.sms_left_chat, _send_sms_no_fail)

    # Remove the sender from the chat room.
    removed_user = room.remove_user(sender)
    smschat.save(only=[models.SmsChat.room])

    # Break the chat connection.
    models.SmsChatConnection.delete().where(
        models.SmsChatConnection.smschat == smschat,
        models.SmsChatConnection.user_number == sender,
        models.SmsChatConnection.relay_number == relay,
    ).execute()

    audit_log.log(
        audit_log.Kind.PARTICIPANT_LEFT_CHAT,
        description=f"{removed_user.name} has left the chat room "
        "with relay number"
        "{removed_user.relay}. "
        "The last 4 digits of the their number is {removed_user.number[-4:]}",
        event=smschat.event,
    )

    # Notify the sender they will no longer get messages.
    lowlevel.send_sms(
        sender=relay, to=sender, message=common_text.sms_stop_request_completed
    )

    return True


def handle_message(sender: str, relay: str, message: str) -> None:
    """Handles an incoming SMS and hands it off to the appropriate room."""

    with models.db.atomic():
        smschat = db.find_smschat_by_user_and_relay_numbers(
            user_number=sender, relay_number=relay
        )

        if smschat:
            room = smschat.room
            if maybe_handle_stop(
                sender=sender, relay=relay, message=message, smschat=smschat
            ):
                return
        else:
            room = _create_room(event_number=relay, reporter_number=sender)

        room.relay(sender, message, _send_sms_no_fail)


def handle_sms_chat_error(err: SmsChatError, sender: str, relay: str):
    if isinstance(err, EventDoesNotExist):
        lowlevel.send_sms(sender=relay, to=sender, message=common_text.sms_no_event)
    elif isinstance(err, NumberBlocked):
        pass
    elif isinstance(err, NoOrganizersAvailable):
        lowlevel.send_sms(sender=relay, to=sender, message=common_text.sms_no_members)
    elif isinstance(err, NoRelaysAvailable):
        lowlevel.send_sms(sender=relay, to=sender, message=common_text.sms_no_relays)
