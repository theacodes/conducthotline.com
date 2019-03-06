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

"""Handles low-level telephony-related actions, such as renting numbers and
sending messages."""

from google.api_core import retry
import nexmo
import phonenumbers

from hotline import injector


def normalize_number(value: str) -> str:
    number = phonenumbers.parse(value, "US")
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)


@injector.provides(
    "nexmo.client",
    needs=[
        "secrets.nexmo.api_key",
        "secrets.nexmo.api_secret",
        "secrets.nexmo.private_key_location",
        "secrets.nexmo.application_id",
    ],
)
def _make_client(api_key, api_secret, private_key_location, application_id):
    return nexmo.Client(
        key=api_key,
        secret=api_secret,
        application_id=application_id,
        private_key=private_key_location,
    )


@injector.needs("nexmo.client")
def setup_number(
    number: str, country: str, sms_callback_url: str, client: nexmo.Client
):
    client.update_number(
        {
            "msisdn": number,
            "country": country,
            "moHttpUrl": sms_callback_url,
            "voiceCallbackType": "app",
            "voiceCallbackValue": client.application_id,
        }
    )


@injector.needs("nexmo.client")
def rent_number(
    sms_callback_url: str, client: nexmo.Client, country_code: str = "US"
) -> dict:
    """Rents a number for the given country.

    NOTE: This immediately charges us for the number (for at least a month).
    """
    numbers = client.get_available_numbers(
        country_code, {"features": "SMS,VOICE", "type": "mobile-lvn"}
    )

    error = RuntimeError("No numbers available.")

    for number in numbers["numbers"]:
        try:
            client.buy_number(
                {"country": number["country"], "msisdn": number["msisdn"]}
            )

            setup_number(
                number=number["msisdn"],
                country=number["country"],
                sms_callback_url=sms_callback_url,
                client=client,
            )

            # Normalize the number.
            number["msisdn"] = normalize_number(number["msisdn"])

            return number

        except nexmo.Error as error:
            continue

    raise error


@injector.needs("nexmo.client")
def get_number_info(number: str, client: nexmo.Client) -> dict:
    return client.get_account_numbers(pattern=number)["numbers"][0]


def _send_sms_retry_predicate(error):
    if isinstance(error, nexmo.ClientError) and "Throughput Rate Exceeded" in str(error):
        return True
    return False


@retry.Retry(predicate=_send_sms_retry_predicate, initial=1.0, deadline=30.0)
@injector.needs("nexmo.client")
def send_sms(sender: str, to: str, message: str, client: nexmo.Client) -> dict:
    """Sends an SMS.

    ``sender`` and ``to`` must be in proper long form.
    """
    # Nexmo is apparently picky about + being in the sender.
    sender = sender.strip("+")

    resp = client.send_message({"from": sender, "to": to, "text": message})

    # Nexmo client incorrectly treats failed messages as successful
    error_text = resp["messages"][0].get("error-text")

    if error_text:
        raise nexmo.ClientError(error_text)

    return resp
