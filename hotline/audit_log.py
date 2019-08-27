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

import enum

from hotline.database import models


@enum.unique
class Kind(enum.IntEnum):
    UNKNOWN = 0
    MEMBER_ADDED = 1
    MEMBER_REMOVED = 2
    EVENT_MODIFIED = 3
    MEMBER_NUMBER_VERIFIED = 4
    SMS_CONVERSATION_STARTED = 5
    VOICE_CONVERSATION_STARTED = 6
    NUMBER_ACQUIRED = 7
    NUMBER_RELEASED = 8
    ORGANIZER_ADDED = 9
    ORGANIZER_REMOVED = 10
    VOICE_CONVERSATION_ANSWERED = 11
    NUMBER_BLOCKED = 12
    NUMBER_UNBLOCKED = 13
    CHAT_DELETED = 14
    PARTICIPANT_LEFT_CHAT = 15


def log(
    kind: Kind,
    description: str,
    event: models.Event = None,
    user: str = None,
    reporter_number: str = None,
) -> None:
    audit_log = models.AuditLog()
    audit_log.kind = kind
    audit_log.description = description
    audit_log.event = event
    audit_log.user = user
    audit_log.reporter_number = reporter_number
    audit_log.save()
