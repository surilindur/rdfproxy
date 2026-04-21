"""Functionality for accessing application configuration."""

from os import getenv
from json import loads
from typing import Dict
from typing import Sequence
from logging import DEBUG
from logging import INFO
from logging import basicConfig
from pathlib import Path
from collections import OrderedDict

from rdflib.term import URIRef
from rdflib.namespace import SDO

QUERY_ENDPOINT = getenv("QUERY_ENDPOINT")
UPDATE_ENDPOINT = getenv("UPDATE_ENDPOINT")
GRAPH_IDENTIFIER = getenv("GRAPH_IDENTIFIER")
SPARQL_USERNAME = getenv("SPARQL_USERNAME")
SPARQL_PASSWORD = getenv("SPARQL_PASSWORD")

# Quad types are disabled, because Web-based querying tools may respect the
# graph terms, and make varying assumptions about how it relates to the current
# document URI, due to the ambiguity surrounding the topic.
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

RDF_PREFIXES: Dict[str, URIRef] = {}

RDF_EXTENSIONS: tuple[str, ...] = (".ttl", ".nq", ".nt", ".rdf", ".jsonld")

QUERY_EXTENSIONS: tuple[str, ...] = (".rq", ".sparql")

TEMPLATE_PATH = Path(getenv("TEMPLATE_PATH", "/usr/share/rdfproxy/templates")).resolve()
TEMPLATE_EXTENSION = getenv("TEMPLATE_EXTENSION", ".jinja")

class SDONew(SDO):  # pylint: disable=too-few-public-methods
    """Temporary helper declaration to include new properties into SDO."""

    errorCode: URIRef
    Error: URIRef


__prefix_path = getenv("PREFIX_PATH")

if __prefix_path:
    prefix_path = Path(__prefix_path).resolve(strict=True)
    with open(prefix_path, "r", encoding="utf-8") as prefix_file:
        prefix_data: Dict[str, str] = loads(prefix_file.read())
        for key, value in prefix_data.items():
            RDF_PREFIXES[key] = URIRef(value)


basicConfig(
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
    level=DEBUG if getenv("FLASK_DEBUG") or getenv("DEBUG") else INFO,
)
