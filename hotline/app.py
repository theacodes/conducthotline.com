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
import hotline.auth.webhandlers
import hotline.telephony.webhandlers

app = flask.Flask(__name__)
app.register_blueprint(hotline.telephony.webhandlers.blueprint)
app.register_blueprint(hotline.auth.webhandlers.blueprint)


# Add a default root route.
@app.route("/")
def index():
    return "Hello"


@app.errorhandler(500)
def server_error(e):
    """TODO: Disable in production."""
    return (
        """
    An internal error occurred: <pre>{}</pre>
    See logs for full stacktrace.
    """.format(
            e
        ),
        500,
    )

    return app
