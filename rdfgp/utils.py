from os import getenv
from http import HTTPStatus
from typing import Any
from typing import Dict
from typing import Tuple
from typing import Iterable
from typing import Sequence
from typing import Callable
from typing import Mapping
from pathlib import Path
from hashlib import sha256
from logging import debug
from datetime import UTC
from datetime import datetime
from functools import wraps
from collections import OrderedDict
from urllib.parse import urlparse

from flask import request
from flask import Response
from flask import render_template

from rdflib.term import URIRef
from rdflib.term import Literal
from rdflib.graph import _SubjectType
from rdflib.graph import _ObjectType
from rdflib.graph import Graph
from rdflib.namespace import RDF
from rdflib.namespace import SDO


class SDONew(SDO):
    """Helper type to add Error and errorCode."""

    errorCode: URIRef
    Error: URIRef


MIMETYPE_KEYWORDS: Dict[str, str] = OrderedDict(
    (
        ("text/turtle", "turtle"),
        ("text/plain", "turtle"),
        ("text/html", "html"),
        ("text/n3", "n3"),
        # ("application/hext", "hext"),
        ("application/ld+json", "json-ld"),
        # ("application/n-quads", "nquads"),
        ("application/n-triples", "nt11"),
        ("application/rdf+xml", "pretty-xml"),
        # ("application/trig", "trig"),
        # ("application/trix", "trix"),
    )
)

MIMETYPE_PRIORITY: Sequence[str] = tuple(MIMETYPE_KEYWORDS.keys())

TEMPLATE_PATH: Path = Path(getenv("TEMPLATE_PATH", "/usr/share/rdfgp")).absolute()

AVAILABLE_TEMPLATES: Mapping[str, str] = {
    fp.name.split(".")[0]: fp.name
    for fp in TEMPLATE_PATH.iterdir()
    if fp.name.endswith(".html")
}


def find_matching_template(graph: Graph) -> Tuple[str | None, str | None]:
    """Helper function to find a matching template."""

    graph_type_names = list(
        t.split("#")[-1].split("/")[-1]
        for t in graph.objects(subject=graph.identifier, predicate=RDF.type)
        if isinstance(t, URIRef)
    )

    graph_type_names.sort(key=lambda t: len(t))

    for type_name in graph_type_names:
        if type_name in AVAILABLE_TEMPLATES:
            return type_name, AVAILABLE_TEMPLATES[type_name]

    return None, None


def content_negotiation(func: Callable[..., Graph]) -> Callable[..., Response]:
    """Helper function to select a response mimetype."""

    @wraps(func)
    def with_content_negotiation(*args: Any, **kwargs: Any) -> Response:

        # Negotiate mimetype if client has preferences, otherwise default to server preference
        negotiated_mimetype = (
            request.accept_mimetypes.best_match(MIMETYPE_PRIORITY)
            if request.accept_mimetypes.provided
            else MIMETYPE_PRIORITY[0]
        )

        # Report content negotiation errors to client without content
        if not negotiated_mimetype:
            return Response(status=HTTPStatus.NOT_ACCEPTABLE)

        output_graph = func(*args, **kwargs)

        if "html" in negotiated_mimetype:
            matching_type, output_template = find_matching_template(graph=output_graph)
            if not matching_type or not output_template:
                return Response(status=HTTPStatus.NOT_EXTENDED)
            output_string = render_template(
                template_name_or_list=output_template,
                graph=output_graph,
                type=matching_type,
                timestamp=datetime.now(tz=UTC),
            )
        else:
            output_string = output_graph.serialize(
                format=MIMETYPE_KEYWORDS[negotiated_mimetype]
            )

        error_code = output_graph.value(
            subject=output_graph.identifier, predicate=SDONew.errorCode
        )
        output_status = (
            int(error_code)
            if isinstance(error_code, Literal) and error_code.isnumeric()
            else HTTPStatus.OK
        )

        return Response(
            response=output_string,
            status=output_status,
            mimetype=negotiated_mimetype,
        )

    return with_content_negotiation  # type: ignore


def get_request_uri() -> URIRef:
    """Helper function to resolve the exact request URI."""

    flask_request_uri = urlparse(request.url)
    proxy_request_host = request.headers.get("X-Forwarded-Host")
    proxy_request_proto = request.headers.get("X-Forwarded-Proto")

    final_proto = proxy_request_proto or flask_request_uri.scheme
    final_host = proxy_request_host or flask_request_uri.hostname

    if flask_request_uri.port:
        final_host = f"{final_host}:{flask_request_uri.port}"

    assert final_host, f"Request data is missing hostname"
    assert ".." not in flask_request_uri.path, "Invalid request path"

    final_uri = URIRef(
        value=flask_request_uri.path,
        base=f"{final_proto}://{final_host}",
    )

    debug(f"Mapped incoming request for <{request.url}> to {final_uri.n3()}")

    return final_uri


def partition_to_fragment(dataset_uri: URIRef, partition_uri: URIRef) -> URIRef:
    """Converts partition URIs from RDFLib's VoID generator into fragments."""

    partition_name = partition_uri.removeprefix(dataset_uri).encode("utf-8")
    partition_hash = sha256(partition_name, usedforsecurity=False).hexdigest()
    partition_fragment = URIRef(value=f"#{partition_hash}", base=dataset_uri)

    return partition_fragment


def sort_by_object(
    subject_objects: Iterable[Tuple[_SubjectType, _ObjectType]],
    reverse: bool = False,
) -> Iterable[_ObjectType]:
    """Jinja filter for sorting subjects based on object value."""

    return (
        so[1]
        for so in sorted(subject_objects, key=lambda so: so[1].n3(), reverse=reverse)
    )
