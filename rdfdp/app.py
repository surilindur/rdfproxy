"""Simple Flask application to serve RDF data as documents from a graph."""

from http import HTTPStatus
from typing import Any
from typing import Dict
from logging import basicConfig
from logging import DEBUG
from logging import INFO
from logging import debug
from logging import error
from logging import warning
from logging import exception
from datetime import datetime
from datetime import timezone
from traceback import format_exc

from flask import Flask
from flask import request
from flask import render_template
from flask import send_file
from flask.wrappers import Response

from werkzeug.exceptions import HTTPException
from werkzeug.exceptions import NotFound
from werkzeug.exceptions import NotAcceptable
from werkzeug.exceptions import BadRequest

from rdflib.term import URIRef
from rdflib.term import Literal
from rdflib.namespace import RDF
from rdflib.namespace import OWL
from rdflib.namespace import SDO

from resources import get_document_datasets
from utils import uri_to_path
from utils import response_ok
from utils import sort_by_predicate
from utils import remove_file_uris
from utils import markdown_to_html
from utils import get_request_url
from templates import load_templates
from templates import find_template
from templates import TEMPLATE_PATH
from constants import ACCEPT_MIMETYPES
from constants import MIMETYPE_FORMATS
from constants import HTTP_HEADER_DATE_FORMAT

# The Flask application, with template clean-ups
app = Flask(import_name=__name__, template_folder=TEMPLATE_PATH)
app.jinja_env.lstrip_blocks = True
app.jinja_env.trim_blocks = True

# Custom filters
app.jinja_env.filters["sort_by_predicate"] = sort_by_predicate  # type: ignore
app.jinja_env.filters["markdown_to_html"] = markdown_to_html  # type: ignore

# Assign the compression defaults based on internal type support
app.config.setdefault("COMPRESS_MIMETYPES", ACCEPT_MIMETYPES)  # type: ignore

# Load configuration from environment variables if available
app.config.from_prefixed_env()

# Configure logging
basicConfig(
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
    level=DEBUG if app.debug else INFO,
)

# Collect the application dataset into cache at the beginning
app_datasets = get_document_datasets()
app_templates = load_templates()
app_startup = datetime.now(tz=timezone.utc)


@app.get("/")
@app.get("/<path:path>")
# pylint: disable-next=unused-argument
def get_document(path: str = "/") -> Response:
    """Return a document-scoped collection of CBDs in the client-preferrec format."""

    # Find the document graph based on original client-facing URI
    document_uri = get_request_url()

    if document_uri not in app_datasets:
        raise NotFound()

    document_graph = app_datasets[document_uri]
    document_mimetype: str | None = None

    available_mimetypes = ACCEPT_MIMETYPES

    # Check if the document is a schema:MediaObject with mimetype
    if (document_uri, RDF.type, SDO.MediaObject) in document_graph:
        document_encoding_format = document_graph.value(
            subject=document_uri,
            predicate=SDO.encodingFormat,
        )
        assert isinstance(
            document_encoding_format, Literal
        ), f"Missing schema:encodingFormat on {document_uri.n3()}"
        document_mimetype = document_encoding_format
        available_mimetypes = tuple(
            (document_mimetype, *(m for m in ACCEPT_MIMETYPES if m != "text/html"))
        )

    mimetype = (
        request.accept_mimetypes.best_match(available_mimetypes)
        if request.accept_mimetypes.provided
        else available_mimetypes[0]
    )

    if not mimetype:
        raise NotAcceptable()

    same_as = document_graph.value(subject=document_uri, predicate=OWL.sameAs)

    if same_as and isinstance(same_as, URIRef):
        return Response(
            status=HTTPStatus.TEMPORARY_REDIRECT,
            headers={"location": same_as},
        )

    if mimetype == document_mimetype:
        document_file_uri = document_graph.value(
            subject=document_uri,
            predicate=SDO.contentUrl,
        )
        assert isinstance(
            document_file_uri, URIRef
        ), f"Missing schema:contentUrl on {document_uri.n3()}"

        document_file_path = uri_to_path(document_file_uri).as_posix()
        debug(f"Serving static document from {document_file_path}")

        # Attempt to use X-Accel-Redirect if enables for nginx
        if app.config.get("USE_X_ACCEL_REDIRECT") in (  # type: ignore
            "true",
            "True",
            True,
            1,
            "1",
        ):
            return Response(
                status=HTTPStatus.OK,
                headers={"X-Accel-Redirect": document_file_path},
                mimetype=mimetype,
            )

        # Fall back to Flask's X-SendFile support
        return send_file(path_or_file=document_file_path, mimetype=mimetype, etag=True)

    format_keyword = MIMETYPE_FORMATS[mimetype]

    # Remove the actual file URI before serving the graph
    document_graph = remove_file_uris(graph=document_graph)

    # Helps identify content negotiation issues
    debug(f"Serving {document_uri.n3()} as {mimetype}")

    if format_keyword == "html":
        document_type_uris = (
            u
            for u in document_graph.objects(
                subject=document_uri,
                predicate=RDF.type,
                unique=True,
            )
            if isinstance(u, URIRef)
        )
        template_name, template_type = find_template(
            uri=document_uri,
            app_templates=app_templates,
            type_uris=document_type_uris,
        )
        if template_name:
            html_string = render_template(
                app_debug=app.debug,
                template_name_or_list=template_name,
                template_type=template_type,
                document_uri=document_uri,
                document_graph=document_graph,
            )
            return Response(response=html_string, mimetype=mimetype)
    else:
        return Response(
            response=document_graph.serialize(format=format_keyword, encoding="utf-8"),
            mimetype=mimetype,
        )

    warning(f"No {format_keyword} template found for {document_uri.n3()}")

    raise NotAcceptable()


@app.before_request
def request_preprocess() -> Response | None:
    """Performs common preprocessing on the request."""

    if request.method in ("GET", "HEAD"):
        # Handle requests with If-Modified-Since
        modified_since_header = request.headers.get("If-Modified-Since")
        if modified_since_header:
            try:
                modified_since_utc = datetime.strptime(
                    modified_since_header,
                    HTTP_HEADER_DATE_FORMAT,
                ).replace(tzinfo=timezone.utc)
            except ValueError as ex:
                error(f'Malformed If-Modified-Since header: "{modified_since_header}"')
                raise BadRequest() from ex
            if app_startup < modified_since_utc:
                return Response(status=HTTPStatus.NOT_MODIFIED)

    return None


@app.after_request
def request_postprocess(response: Response) -> Response:
    """Performs common postprocessing on the response."""

    if response_ok(response.status_code) and request.method in ("GET", "HEAD"):
        response.headers.set(
            "Last-Modified",
            app_startup.strftime(HTTP_HEADER_DATE_FORMAT),
        )

    if app.debug and "Origin" in request.headers:
        response.headers.set("Access-Control-Allow-Origin", request.headers["Origin"])
        response.headers.set("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        response.headers.set("Access-Control-Allow-Credentials", "true")

    return response


@app.context_processor
def handle_context() -> Dict[str, Any]:
    """Add various utility types into the template context."""
    return {"current_year": datetime.now(tz=timezone.utc).year}


@app.errorhandler(Exception)
def handle_error(exc: Exception) -> Response:
    """Return a representation of a server error."""

    response: str | None = None

    if isinstance(exc, HTTPException):
        status_code = exc.code
        status_name = exc.name
        status_description = exc.description
    else:
        exception(exc)
        status_code = HTTPStatus.INTERNAL_SERVER_ERROR.value
        status_name = HTTPStatus.INTERNAL_SERVER_ERROR.phrase
        status_description = HTTPStatus.INTERNAL_SERVER_ERROR.description

    if request.accept_mimetypes.provided and "text/html" in request.accept_mimetypes:
        try:
            document_uri = get_request_url()
            template_name, template_type = find_template(
                uri=document_uri,
                app_templates=app_templates,
                http_status=HTTPStatus(value=status_code),
            )
            if template_name:
                html_string = render_template(
                    app_debug=app.debug,
                    template_name_or_list=template_name,
                    template_type=template_type,
                    error_code=status_code,
                    error_title=status_name,
                    error_description=status_description,
                    error_message=format_exc() if app.debug else str(exc),
                )
                return Response(response=html_string, mimetype="text/html")
            warning(f"Unable to find error template for {document_uri.n3()}")
        # pylint: disable-next=broad-exception-caught
        except Exception as ex:
            error(ex)

    return Response(response=response, status=status_code)
