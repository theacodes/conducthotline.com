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

import flask

import hotline.database.ext
from hotline import injector
from hotline.database import highlevel as db
from hotline.telephony import lowlevel
from hotline.telephony import verification

blueprint = flask.Blueprint("telephony", __name__)
hotline.database.ext.init_app(blueprint)


@blueprint.route("/telephony/inbound-sms", methods=["POST"])
@injector.needs("secrets.virtual_number")
def inbound_sms(virtual_number):
    # TODO: Probably validate this.
    message = flask.request.get_json()
    user_number = message["msisdn"]
    relay_number = message["to"]
    message_text = message["text"]

    # Maybe handle verification, if this is a response to a verification message.
    if verification.maybe_handle_verification(user_number, message_text):
        return "", 204

    # okay, it wasn't a verification text - pass it on to the right hotline.
    room = db.find_room_for_user(user_number=user_number, relay_number=relay_number)

    if not room:
        print("Uh oh, no room found for message: ", message)
        return "", 204

    room.relay(user_number, message_text, lowlevel.send_sms)

    return "", 204
