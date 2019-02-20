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

from hotline.auth import auth_required
from hotline.database import highlevel as db

blueprint = flask.Blueprint("events", __name__, template_folder="templates")


@blueprint.route("/events")
@auth_required
def list_events():
    events = db.list_events()
    return flask.render_template("list.html", events=events)
