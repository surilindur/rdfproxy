"""Utiliies for templates."""

from http import HTTPStatus
from typing import Set
from typing import Tuple
from typing import Dict
from typing import Iterable
from logging import debug
from os.path import splitext
from functools import cache
from urllib.parse import urlparse

from rdflib.term import URIRef

from utils import env_to_path
from utils import find_files
from utils import response_ok

# List of acceptable template extensions
TEMPLATE_EXTENSIONS: Set[str] = set((".html",))

# Path to templates
TEMPLATE_PATH = env_to_path("TEMPLATE_PATH")

# Defaults
DEFAULT_DOMAIN = "@defaultdomain"


@cache
def load_templates() -> Dict[str, Dict[str, str]]:
    """Loads all the templates of the application."""

    templates: Dict[str, Dict[str, str]] = {}

    for path in find_files(TEMPLATE_PATH, TEMPLATE_EXTENSIONS):
        path_name = splitext(path.name)[0]
        path_domain = (
            DEFAULT_DOMAIN if path.parent == TEMPLATE_PATH else path.parent.name
        )
        if path_domain not in templates:
            templates[path_domain] = {}
        templates[path_domain][path_name] = path.relative_to(TEMPLATE_PATH).as_posix()

    return templates


def find_template(
    uri: URIRef,
    app_templates: Dict[str, Dict[str, str]],
    type_uris: Iterable[URIRef] | None = None,
    http_status: HTTPStatus | None = None,
) -> Tuple[str | None, str | None]:
    """Attempts to locate the template for a resource with the specified types."""

    uri_domain = urlparse(uri).hostname
    domain = uri_domain if uri_domain in app_templates else DEFAULT_DOMAIN

    if domain in app_templates:
        domain_templates = app_templates[domain]
        template_path: str | None = None
        type_name: str | None = None

        if type_uris:
            for type_uri in sorted(type_uris):
                type_uri_parsed = urlparse(type_uri)
                type_name = (
                    type_uri_parsed.fragment or type_uri_parsed.path.split("/")[-1]
                )
                if type_name in domain_templates:
                    template_path = domain_templates[type_name]

        elif http_status:
            template_name = f"_{http_status.value}"
            if template_name in domain_templates:
                template_path = domain_templates[template_name]
                type_name = str(http_status.value)
            elif not response_ok(http_status.value) and "_error" in domain_templates:
                template_path = domain_templates["_error"]
                type_name = "Error"

        if template_path and type_name:
            debug(f"Mapped {uri.n3()} to template {template_path}")
            return template_path, type_name

    return None, None
