"""Functionality for accessing application configuration."""

from os import getenv
from json import loads
from typing import Dict
from typing import Sequence
from pathlib import Path
from collections import OrderedDict

from rdflib.term import URIRef
from rdflib.namespace import SDO

SPARQL_GRAPH = getenv("SPARQL_GRAPH")
SPARQL_USERNAME = getenv("SPARQL_USERNAME")
SPARQL_PASSWORD = getenv("SPARQL_PASSWORD")
SPARQL_ENDPOINT = getenv("SPARQL_ENDPOINT")

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
TEMPLATE_PATH = Path(getenv("TEMPLATE_PATH", "/usr/share/rdfproxy/templates")).resolve(
    strict=True
)


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
