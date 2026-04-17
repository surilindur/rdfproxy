"""Miscellaneous utility functionality."""

from http import HTTPStatus
from json import dumps
from typing import Any
from typing import Tuple
from typing import Set
from typing import List
from typing import Iterable
from typing import Callable
from typing import Mapping
from hashlib import sha256
from logging import debug
from pathlib import Path
from datetime import UTC
from datetime import datetime
from functools import cache
from functools import wraps
from urllib.parse import urlparse

from flask import request
from flask import Response
from flask import render_template

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

from rdflib.term import URIRef
from rdflib.term import Literal
from rdflib.graph import _SubjectType
from rdflib.graph import _ObjectType
from rdflib.graph import Graph
from rdflib.namespace import RDF
from rdflib.namespace import OWL

from config import SDONew
from config import MIMETYPE_KEYWORDS
from config import MIMETYPE_PRIORITY
from config import TEMPLATE_PATH
from config import TEMPLATE_EXTENSION

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


@cache
def get_available_templates(host: str) -> Mapping[str, Path]:
    """Helper function to collect available templates."""

    templates: Mapping[str, Path] = {}

    host_directory = ".".join(host.split(":")[0].split(".")[::-1])
    host_template_path = TEMPLATE_PATH.joinpath(host_directory).resolve()

    if not host_template_path.exists() or not host_template_path.is_dir():
        debug(f"Host templates not found at {host_template_path}")
        host_template_path = TEMPLATE_PATH

    assert TEMPLATE_PATH in (
        host_template_path,
        host_template_path.parent,
    ), f"Malformed host template path {host_template_path}"

    debug(f"Using templates for host {host} from {host_template_path}")

    for fp in host_template_path.iterdir():
        if fp.name.endswith(TEMPLATE_EXTENSION):
            templates[fp.name.removesuffix(TEMPLATE_EXTENSION)] = fp

    return templates


def find_matching_template(graph: Graph) -> Tuple[str | None, Path | None]:
    """Helper function to find a matching template."""

    type_names: Set[str] = set()
    templates = get_available_templates(request.host)

    for type_term in graph.objects(subject=graph.identifier, predicate=RDF.type):
        if isinstance(type_term, URIRef):
            type_name = type_term.split("#")[-1].split("/")[-1]
            type_names.add(type_name)

    for type_name in sorted(type_names):
        if type_name in templates:
            return type_name, templates[type_name]

    return None, None


def content_negotiation(func: Callable[..., Graph]) -> Callable[..., Response]:
    """Helper function to select a response mimetype."""

    @wraps(func)
    def with_content_negotiation(*args: Any, **kwargs: Any) -> Response:

        # Negotiate mimetype if client has preferences,
        # otherwise default to server preference
        negotiated_mimetype = (
            request.accept_mimetypes.best_match(MIMETYPE_PRIORITY)
            if request.accept_mimetypes.provided
            else MIMETYPE_PRIORITY[0]
        )

        # Report content negotiation errors to client without content
        if not negotiated_mimetype:
            return Response(status=HTTPStatus.NOT_ACCEPTABLE)

        output_graph = func(*args, **kwargs)

        redirect_to = output_graph.value(
            subject=output_graph.identifier,
            predicate=OWL.sameAs,
        )

        if redirect_to and isinstance(redirect_to, URIRef):
            debug(f"Redirecting to {redirect_to.n3()}")
            return Response(
                status=HTTPStatus.FOUND,
                headers={"Location": redirect_to},
            )

        if "html" in negotiated_mimetype:
            matching_type, output_template = find_matching_template(graph=output_graph)
            if not matching_type or not output_template:
                return Response(status=HTTPStatus.NOT_EXTENDED)
            template_name = str(output_template.relative_to(TEMPLATE_PATH))
            debug(f"Serialising {output_graph.identifier.n3()} using {template_name}")
            output_string = render_template(
                template_name_or_list=template_name,
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

    final_host = proxy_request_host or flask_request_uri.netloc
    final_proto = proxy_request_proto or flask_request_uri.scheme

    assert final_host, "Request data is missing hostname"
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


def markdown_to_html(content: str) -> str:
    """Jinja filter to convert markdown into HTML."""

    html_output = mistune_markdown(content)

    if isinstance(html_output, str):
        return html_output

    html_json = dumps(html_output, ensure_ascii=False, indent=2, sort_keys=True)

    return f"<pre>{html_json}</pre>"


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


def iterate_by_extension(path: Path, extensions: tuple[str, ...]) -> Iterable[Path]:
    """Helper function to recursively iterate over files with extensions."""

    queue: List[Path] = [path]

    while queue:
        path = queue.pop(0)
        if path.is_file() and path.name.endswith(extensions):
            yield path
        elif path.is_dir():
            queue.extend(path.iterdir())
