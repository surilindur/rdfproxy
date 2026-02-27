"""Simple proxy application to serve RDF resources as Web documents."""

from logging import exception

from flask import Flask
from flask import request

from werkzeug.exceptions import HTTPException
from werkzeug.exceptions import InternalServerError
from werkzeug.exceptions import default_exceptions

from rdflib.term import Literal
from rdflib.graph import Graph
from rdflib.namespace import RDF
from rdflib.namespace import SDO

from store import get_document
from utils import content_negotiation
from utils import get_request_uri
from utils import sort_by_object
from utils import markdown_to_html
from config import SDONew
from config import MIMETYPE_PRIORITY
from config import TEMPLATE_PATH

app = Flask(import_name=__name__, template_folder=TEMPLATE_PATH)
app.jinja_env.lstrip_blocks = True
app.jinja_env.trim_blocks = True

# Custom filters for templates
app.jinja_env.filters["sort_by_object"] = sort_by_object  # type: ignore
app.jinja_env.filters["markdown_to_html"] = markdown_to_html  # type: ignore

# Ensure custom mimetypes are compressed
app.config.setdefault("COMPRESS_MIMETYPES", MIMETYPE_PRIORITY)  # type: ignore

# Load configuration from environment variables if available
app.config.from_prefixed_env()


@app.route("/")
@app.route("/<path:path>")
@content_negotiation
def document(path: str = "/") -> Graph:
    """Serve a document graph."""

    request_uri = get_request_uri()
    assert request_uri.endswith(path), f"Invalid mapping of {path} to {request_uri}"
    document_graph = get_document(request_uri)

    return document_graph


@app.errorhandler(Exception)
@app.errorhandler(HTTPException)
@content_negotiation
def errorhandler(code_or_exception: type[Exception] | int) -> Graph:
    """Serve an error representation graph."""

    if isinstance(code_or_exception, int) and code_or_exception in default_exceptions:
        code_or_exception = default_exceptions[code_or_exception]

    if isinstance(code_or_exception, HTTPException):
        error_code = Literal(code_or_exception.code)
        error_name = Literal(code_or_exception.name)
        error_description = Literal(code_or_exception.description)
    else:
        exception(code_or_exception)
        error_temp = InternalServerError()
        error_code = Literal(error_temp.code)
        error_name = Literal(error_temp.name)
        error_description = Literal(error_temp.description)

    # See: https://schema.org/Error
    error_graph = Graph(identifier=request.url)
    error_graph.add((error_graph.identifier, RDF.type, SDONew.Error))
    error_graph.add((error_graph.identifier, SDONew.errorCode, error_code))
    error_graph.add((error_graph.identifier, SDO.name, error_name))
    error_graph.add((error_graph.identifier, SDO.description, error_description))

    return error_graph
