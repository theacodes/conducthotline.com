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

import phonenumbers
import wtforms

from hotline import common_text


class EventEditForm(wtforms.Form):
    name = wtforms.StringField(
        "Event name", validators=[wtforms.validators.InputRequired()]
    )
    slug = wtforms.StringField(
        "URL Slug",
        description="Used to generate a URL for your event. For example, https://conducthotline/e/pycascades.",
        validators=[wtforms.validators.InputRequired()],
    )
    coc_link = wtforms.StringField(
        description="Displayed on the public view for your event. Should be a full URL, including https://."
    )
    website = wtforms.StringField(
        description="Displayed on the public view for your event. Should be a full URL, including https://."
    )
    contact_email = wtforms.StringField(
        description="Displayed on the public view for your event."
    )
    location = wtforms.StringField(
        description="Displayed on the public view for your event."
    )
    voice_greeting = wtforms.TextField(
        description=f"Spoken when a person calls the hotline. By default, this is <code>{common_text.voice_default_greeting}</code>."
    )
    sms_greeting = wtforms.TextField(
        description=f"Sent when a person texts the hotline. By default, this is <code>{common_text.sms_default_greeting}</code>."
    )


def validate_phone_number(form, field):
    try:
        number = phonenumbers.parse(field.data, "US")

    except phonenumbers.NumberParseException:
        raise wtforms.ValidationError(
            f"{field.data} does not appear to be a valid number."
        )

    if not phonenumbers.is_possible_number(number):
        raise wtforms.ValidationError(
            f"{field.data} does not appear to be a possible number."
        )

    field.data = phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)


class AddMemberForm(wtforms.Form):
    name = wtforms.StringField("Name", validators=[wtforms.validators.InputRequired()])
    number = wtforms.StringField(
        "Number", validators=[wtforms.validators.InputRequired(), validate_phone_number]
    )


class AddOrganizerForm(wtforms.Form):
    email = wtforms.StringField(
        "Email", validators=[wtforms.validators.InputRequired()]
    )
