"""Simple Flask application to serve RDF documents from a SPARQL endpoint."""

from re import sub
from os import getenv
from http import HTTPStatus
from typing import cast
from typing import Dict
from typing import Tuple
from typing import Iterable
from logging import getLogger
from datetime import UTC
from datetime import datetime
from platform import python_version
from platform import system
from platform import machine
from platform import python_implementation
from collections import OrderedDict
from urllib.parse import urlparse
from urllib.parse import ParseResult
from wsgiref.handlers import format_date_time

from flask import g
from flask import request
from flask import abort
from flask import render_template
from flask import Flask
from flask import Response

from orjson import loads
from orjson import dumps

from werkzeug.exceptions import HTTPException
from werkzeug.exceptions import InternalServerError
from werkzeug.exceptions import default_exceptions

from rdflib import __version__
from rdflib.util import parse_date_time
from rdflib.term import URIRef
from rdflib.term import Literal
from rdflib.graph import Graph
from rdflib.graph import _SubjectType
from rdflib.graph import _ObjectType
from rdflib.namespace import RDF
from rdflib.namespace import SDO
from rdflib.namespace import OWL

from mistune.markdown import Markdown
from mistune.plugins.abbr import abbr
from mistune.plugins.def_list import def_list
from mistune.plugins.footnotes import footnotes
from mistune.plugins.formatting import mark
from mistune.plugins.formatting import strikethrough
from mistune.plugins.formatting import subscript
from mistune.plugins.formatting import superscript
from mistune.plugins.math import math
from mistune.plugins.table import table
from mistune.renderers.html import HTMLRenderer

from sparqlx.sparqlwrapper import SPARQLWrapper


class SDONew(SDO):
    """Helper extension to add new entries."""

    Error: URIRef
    errorCode: URIRef


app = Flask(import_name=__name__)
app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True
app.config.from_prefixed_env()

sparql_wrapper = SPARQLWrapper(
    sparql_endpoint=cast(str, app.config["SPARQL_ENDPOINT"]),
    query_method="POST-direct",
    client_config={
        "http2": True,
        "headers": {
            "User-Agent": getenv(
                "FLASK_USER_AGENT",
                " ".join(
                    (
                        f"RDFProxy/0.1 ({system()}, {machine()})",
                        f"RDFLib/{__version__}",
                        f"{python_implementation()}/{python_version()}",
                    )
                ),
            )
        },
    },
)

mimetype_keywords = OrderedDict(
    (
        ("text/turtle", "turtle"),
        ("text/plain", "turtle"),
        ("text/n3", "n3"),
        ("application/n-triples", "nt11"),
        ("application/rdf+xml", "pretty-xml"),
        ("application/ld+json", "json-ld"),
        ("text/html", "html"),
    )
)

charset_preference = ("utf-8", "utf-16")
mimetype_preference = tuple(mimetype_keywords.keys())

prefix_path = getenv("FLASK_PREFIXES")
prefix_mapping: Dict[str, URIRef] = {}

if prefix_path:
    with open(prefix_path, "r", encoding="utf-8") as prefix_file:
        prefix_data = cast(Dict[str, str], loads(prefix_file.read()))
        for key, value in prefix_data.items():
            prefix_mapping[key] = URIRef(value)

document_graph_query = sub(
    r"\s+",
    " ",
    """
    CONSTRUCT {
            ?s ?p ?o .
    } WHERE {
        ?s ?p ?o .

        FILTER(
            isIRI(?s) &&
            ((?s = ?document) || STRSTARTS(STR(?s), CONCAT(STR(?document), "#")))
        )

        VALUES ?document { ?document_uri }
    }
    """,
)

mistune_renderer = HTMLRenderer()
mistune_markdown = Markdown(
    renderer=mistune_renderer,
    plugins=[
        abbr,
        def_list,
        footnotes,
        mark,
        math,
        strikethrough,
        subscript,
        superscript,
        table,
    ],
)


@app.before_request
def content_negotiation() -> None:
    """Performs content negotiation before any other processing."""

    # Negotiate HTML Content-Type for the response
    if request.accept_mimetypes.provided:
        g.mimetype = request.accept_mimetypes.best_match(mimetype_preference)
    else:
        g.mimetype = mimetype_preference[0]

    if not isinstance(g.mimetype, str):
        abort(HTTPStatus.NOT_ACCEPTABLE)

    # Negotiate charset, but only accept UTF-8
    if request.accept_charsets.provided:
        g.charset = request.accept_charsets.best_match(charset_preference)
    else:
        g.charset = charset_preference[0]

    if not isinstance(g.charset, str):
        abort(HTTPStatus.NOT_ACCEPTABLE)

    parsed_uri = urlparse(request.url)
    request_uri = ParseResult(
        scheme=request.headers.get("X-Forwarded-Proto", parsed_uri.scheme),
        netloc=request.headers.get("X-Forwarded-Host", parsed_uri.netloc),
        path=parsed_uri.path,
        params=parsed_uri.params,
        query=parsed_uri.query,
        fragment=parsed_uri.fragment,
    )

    if request_uri.query or request_uri.fragment or request_uri.params:
        abort(HTTPStatus.BAD_REQUEST)

    g.document_uri = URIRef(request_uri.geturl())


@app.after_request
def adjust_headers(response: Response) -> Response:
    """
    Remove unnecessary Content-Type header when the response is empty,
    and add missing Last-Modified header when the response is not empty.

    See: https://datatracker.ietf.org/doc/html/rfc2616#section-7.2.1
    """

    if response.content_length == 0:
        response.headers.remove("Content-Type")
    elif not response.headers.get("Last-Modified"):
        response.headers.set(
            "Last-Modified",
            format_date_time(datetime.now(tz=UTC).timestamp()),
        )

    return response


@app.route("/")
@app.route("/<path:path>")
def serve_document(**_) -> Response:
    """Serves a document, either as RDF or using an HTML template."""

    document_graph = Graph(identifier=cast(URIRef, g.document_uri))
    document_graph += cast(
        Graph,
        sparql_wrapper.query(
            query=document_graph_query.replace(
                "?document_uri",
                document_graph.identifier.n3(),
            ),
            convert=True,
        ),
    )
    if not document_graph:
        abort(HTTPStatus.NOT_FOUND)
    if g.mimetype == "text/html":
        try:
            result_string = render_template(
                template_name_or_list=list(
                    f"{t.rsplit("/", 1)[-1].split("#")[-1]}.jinja"
                    for t in document_graph.objects(
                        subject=document_graph.identifier, predicate=RDF.type
                    )
                    if isinstance(t, URIRef)
                ),
                timestamp=datetime.now(tz=UTC),
                graph=document_graph,
            )
        except:
            abort(HTTPStatus.NOT_EXTENDED)
    else:
        result_string = document_graph.serialize(format=mimetype_keywords[g.mimetype])

    # Check if the document has been redirected elsewhere
    document_same_as = document_graph.value(
        subject=document_graph.identifier,
        predicate=OWL.sameAs,
    )

    if isinstance(document_same_as, URIRef):
        return Response(
            status=HTTPStatus.TEMPORARY_REDIRECT,
            headers={"Location": document_same_as},
        )

    # Determine the modification date of the document, if available
    document_modified = (
        document_graph.value(
            subject=document_graph.identifier,
            predicate=SDO.dateModified,
        )
        or document_graph.value(
            subject=document_graph.identifier,
            predicate=SDO.datePublished,
        )
        or document_graph.value(
            subject=document_graph.identifier,
            predicate=SDO.dateCreated,
        )
    )

    modified_time = (
        datetime.fromtimestamp(parse_date_time(document_modified), tz=UTC)
        if isinstance(document_modified, Literal)
        else datetime.now(tz=UTC)
    )

    return Response(
        response=result_string.encode(encoding=g.charset),
        status=HTTPStatus.OK,
        headers={
            "Content-Type": f"{g.mimetype}; charset={g.charset}",
            "Last-Modified": format_date_time(modified_time.timestamp()),
        },
    )


@app.errorhandler(Exception)
@app.errorhandler(HTTPException)
def errorhandler(code_or_exception: type[Exception] | int) -> Response:
    """Serves an error, either as RDF or using an HTML template."""

    status: int | None = None

    if isinstance(code_or_exception, int) and code_or_exception in default_exceptions:
        status = code_or_exception
        code_or_exception = default_exceptions[code_or_exception]

    if isinstance(code_or_exception, HTTPException):
        status = code_or_exception.code or status
        error_code = Literal(code_or_exception.code)
        error_name = Literal(code_or_exception.name)
        error_description = Literal(code_or_exception.description)
    else:
        getLogger("werkzeug").exception(code_or_exception)
        error_temp = InternalServerError()
        error_code = Literal(error_temp.code)
        error_name = Literal(error_temp.name)
        error_description = Literal(error_temp.description)
        status = error_temp.code or status

    # See: https://schema.org/Error
    error_graph = Graph(identifier=request.url)
    error_graph.add((error_graph.identifier, RDF.type, SDONew.Error))
    error_graph.add((error_graph.identifier, SDONew.errorCode, error_code))
    error_graph.add((error_graph.identifier, SDO.name, error_name))
    error_graph.add((error_graph.identifier, SDO.description, error_description))

    try:
        charset = g.charset or "utf-8"
        datetime_now = datetime.now(tz=UTC)
        if g.mimetype == "text/html":
            content_string = render_template(
                template_name_or_list="Error.jinja",
                timestamp=datetime_now,
                graph=error_graph,
            )
        else:
            content_string = error_graph.serialize(format=mimetype_keywords[g.mimetype])
        return Response(
            status=status,
            response=content_string.encode(encoding=charset),
            headers={"Content-Type": f"{g.mimetype}; charset={charset}"},
        )
    except:
        return Response(status=status)


@app.template_filter()
def markdown_to_html(content: str) -> str:
    """Jinja filter to convert markdown into HTML."""

    html_output = mistune_markdown(content)

    if isinstance(html_output, str):
        return html_output

    return f"<pre>{dumps(html_output)}</pre>"


@app.template_filter()
def sort_by_object(
    subject_objects: Iterable[Tuple[_SubjectType, _ObjectType]],
    reverse: bool = False,
) -> Iterable[_SubjectType]:
    """Jinja filter for sorting subjects based on object value."""

    return (
        so[0]
        for so in sorted(
            subject_objects,
            key=lambda so: so[1].n3(),
            reverse=reverse,
        )
    )
