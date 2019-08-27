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


voice_no_event = "No event was found for this number. Please reach out to the event staff directly for assistance."
voice_blocked = "This number is currently unavailable."
voice_no_members = "Unfortunately, there are no verified members for this event's hotline. Please reach out to the event staff directly for assistance."
voice_default_greeting = "Thank you for calling the Code of Conduct hotline for {event.name}. This will dial all of the hotline members and put you on hold until one is able to answer."
voice_answer_error = "Oh no, an error occurred and we couldn't find the event or member entry for this call."
voice_answer_announce = "{member.name} is joining this call."
voice_answer_greeting = "Hello {member.name}, connecting you to {event.name}."

sms_no_event = "Sorry, there doesn't seem to be an event configured for that number."
sms_no_members = "Sorry, there aren't any organizers currently available. Please reach out to the event staff in person for assistance."
sms_no_relays = "Sorry, there aren't any relays available to send your message. You can try calling the hotline or reaching out to the event staff in person for assistance."
sms_default_greeting = (
    "You have started a new chat with the organizers of {event.name}."
)
sms_introduction = "This is the beginning of a new chat for {event.name}, the last 4 digits of the reporter's number are {reporter_number}."
sms_stop_request_completed = "You've been successfully unsubscribed, you'll no longer receive messages from this number."
sms_left_chat = "This participant has chosen to leave the chat."
