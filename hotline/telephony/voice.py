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


"""Handles calling the hotline.

Calling a hotline connects the caller to all of the verified event members.
"""

from typing import List

import nexmo

from hotline import audit_log, injector
from hotline.database import highlevel as db

HOLD_MUSIC = "https://assets.ctfassets.net/j7pfe8y48ry3/530pLnJVZmiUu8mkEgIMm2/dd33d28ab6af9a2d32681ae80004886e/oaklawn-dreams.mp3"


@injector.needs("nexmo.client")
def handle_inbound_call(
    event_number: str,
    conversation_uuid: str,
    call_uuid: str,
    host: str,
    client: nexmo.Client,
) -> List[dict]:
    # Get the event. If there's no event, tell the user that something went
    # wrong.
    event = db.get_event_by_number(event_number)

    if event is None:
        error_ncco = [
            {
                "action": "talk",
                "text": "No event was found for this number. Please reach out to the event staff directly for assistance.",
            }
        ]
        return error_ncco

    # Get the members for the event. If there are no members, tell the user. :(
    event_members = list(db.get_verified_event_members(event))

    if not event_members:
        error_ncco = [
            {
                "action": "talk",
                "text": (
                    "Unfortunately, there are no verified members for this event's hotline. "
                    "Please reach out to the event staff directly for assistance."
                ),
            }
        ]
        return error_ncco

    # Great, we have an event. Greet the user.
    greeting = (
        f"Thank you for calling the Code of Conduct hotline for {event.name}. This will dial all "
        f"of the hotline members and put you on hold until one is able to answer."
    )

    # NCCOs to be given to the caller.
    reporter_nccos: List[dict] = []

    # Greet the reporter.
    reporter_nccos.append({"action": "talk", "text": greeting})

    # Start a "conversation" (conference call)
    reporter_nccos.append(
        {
            "action": "conversation",
            "name": conversation_uuid,
            "eventMethod": "POST",
            "musicOnHoldUrl": [HOLD_MUSIC],
            "endOnExit": False,
            "startOnEnter": False,
        }
    )

    # Add all of the event members to the conference call.
    for member in event_members:
        client.create_call(
            {
                "to": [{"type": "phone", "number": member.number}],
                "from": {"type": "phone", "number": event.primary_number},
                "answer_url": [
                    f"https://{host}/telephony/connect-to-conference/{conversation_uuid}/{call_uuid}"
                ],
                "answer_method": "POST",
            }
        )

    audit_log.log(
        audit_log.Kind.VOICE_CONVERSATION_STARTED,
        description=f"A new voice conversation was started, uuid is {conversation_uuid}",
        event=event,
    )

    return reporter_nccos


@injector.needs("nexmo.client")
def handle_member_answer(
    event_number: str,
    member_number: str,
    origin_conversation_uuid: str,
    origin_call_uuid: str,
    client: nexmo.Client,
):
    """Connects an organizer to a call-in-progress when they answer."""

    # Members can actually be part of multiple events, so look up the event
    # separately.
    member = db.get_member_by_number(member_number)
    event = db.get_event_by_number(event_number)

    if member is None or event is None:
        error_ncco = [
            {
                "action": "talk",
                "text": (
                    "Oh no, an error occurred and we couldn't find the event or "
                    "member entry for this call."
                ),
            }
        ]
        return error_ncco

    client.send_speech(origin_call_uuid, text=f"{member.name} is joining this call.")

    ncco = [
        {
            "action": "talk",
            "text": f"Hello {member.name}, connecting you to {event.name}.",
        },
        {
            "action": "conversation",
            "name": origin_conversation_uuid,
            "startOnEnter": True,
            "endOnExit": True,
        },
    ]

    audit_log.log(
        audit_log.Kind.VOICE_CONVERSATION_ANSWERED,
        description=f"{member.name} answered {origin_conversation_uuid}.",
        user="{member.name}",
        event=event,
    )

    return ncco
