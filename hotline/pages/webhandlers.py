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

import os

import cmarkgfm
import flask
import flask.helpers

HERE = os.path.dirname(__file__)
CONTENT = os.path.join(HERE, "content")

blueprint = flask.Blueprint("pages", __name__, template_folder="templates")


@blueprint.route("/pages/<name>")
def view_page(name):
    markdown_file = flask.safe_join(CONTENT, f"{name}.md")

    if not os.path.exists(markdown_file):
        flask.abort(404)

    with open(markdown_file, "r") as fh:
        content = cmarkgfm.markdown_to_html_with_extensions(
            fh.read(), extensions=["table", "autolink", "strikethrough"]
        )

    # content = content.replace("<h1>", "<h1 class=\"title is-1 is-spaced\">")
    # content = content.replace("<h2>", "<h2 class=\"subtitle is-2 is-spaced\">")

    return flask.render_template("page.html", content=content)
