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
from hotline.telephony import lowlevel, smschat, verification, voice

blueprint = flask.Blueprint("telephony", __name__)
hotline.database.ext.init_app(blueprint)


@blueprint.route("/telephony/inbound-sms", methods=["POST"])
def inbound_sms():
    message = flask.request.get_json()
    user_number = lowlevel.normalize_number(message["msisdn"])
    relay_number = lowlevel.normalize_number(message["to"])
    message_text = message["text"]

    # Maybe handle verification, if this is a response to a verification message.
    if verification.maybe_handle_verification(user_number, message_text):
        return "", 204

    # It's not verification, so hand it off to SMS chat
    try:
        smschat.handle_message(user_number, relay_number, message_text)
    except smschat.SmsChatError as err:
        smschat.handle_sms_chat_error(err, user_number, relay_number)

    return "", 204


HOLD_MUSIC = "https://assets.ctfassets.net/j7pfe8y48ry3/530pLnJVZmiUu8mkEgIMm2/dd33d28ab6af9a2d32681ae80004886e/oaklawn-dreams.mp3"


@blueprint.route("/telephony/inbound-call", methods=["POST"])
@injector.needs("nexmo.client")
def inbound_call(client):
    call = flask.request.get_json()
    event_number = lowlevel.normalize_number(call["to"])
    conversation_uuid = call["conversation_uuid"]
    call_uuid = call["uuid"]

    ncco = voice.handle_inbound_call(
        event_number=event_number,
        conversation_uuid=conversation_uuid,
        call_uuid=call_uuid,
        host=flask.request.host,
    )

    return flask.jsonify(ncco)


@blueprint.route(
    "/telephony/connect-to-conference/<origin_conversation_uuid>/<origin_call_uuid>",
    methods=["POST"],
)
@injector.needs("nexmo.client")
def connect_to_conference(origin_conversation_uuid, origin_call_uuid, client):
    call = flask.request.get_json()
    member_number = lowlevel.normalize_number(call["to"])
    event_number = lowlevel.normalize_number(call["from"])

    ncco = voice.handle_member_answer(
        event_number=event_number,
        member_number=member_number,
        origin_conversation_uuid=origin_conversation_uuid,
        origin_call_uuid=origin_call_uuid,
    )

    return flask.jsonify(ncco)


@blueprint.route("/telephony/event", methods=["POST"])
def event():
    # For now, we do nothing with these events, but this is required by
    # nexmo.
    return "", 204
