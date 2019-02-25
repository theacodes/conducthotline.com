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

"""Methods for verifying numbers."""

from hotline import injector
from hotline.database import highlevel as db
from hotline.telephony import lowlevel


@injector.needs("secrets.virtual_number")
def _get_sender_for_member(member, virtual_number: str):
    # Try to send from the event number, if it has one.
    if member.event.primary_number:
        return member.event.primary_number

    # If not, send from the hotline's number.
    return virtual_number


def start_member_verification(member):
    sender = _get_sender_for_member(member)

    message = f"You've been added as a member of the {member.event.name} event on conducthotline.com. Reply with YES or OK to confirm."

    lowlevel.send_sms(sender, member.number, message)


def maybe_handle_verification(member_number: str, message: str):
    """Checks if the message is a verification message for the given number."""
    pending_member_record = db.find_pending_member_by_number(member_number)

    if not pending_member_record:
        return False

    if message.strip().lower() not in ("ok", "yes", "okay"):
        print(f"Verification message was not okay, was {message}")
        # This was "handled", even though verification wasn't approved.
        return True

    pending_member_record.verified = True
    pending_member_record.save()

    sender = _get_sender_for_member(pending_member_record)

    reply = "Thank you, your number is confirmed."

    lowlevel.send_sms(sender, member_number, reply)

    return True
