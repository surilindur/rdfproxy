from os import getenv
from http import HTTPStatus
from typing import Mapping
from logging import debug
from platform import python_version
from platform import system
from platform import machine
from platform import python_implementation
from functools import cache

from flask import abort

from rdflib import __version__
from rdflib.term import URIRef
from rdflib.term import Variable
from rdflib.graph import Graph
from rdflib.store import Store
from rdflib.plugins.stores.sparqlstore import SPARQLStore

RESOURCE_VARIABLE: Variable = Variable("resource")
DOCUMENT_VARIABLE: Variable = Variable("document")

CUSTOM_PREFIXES: Mapping[str, str] = {
    "solid": "http://www.w3.org/ns/solid/terms#",
}


@cache
def get_store() -> Store:
    """Connect to the SPARQL store."""

    username = getenv("SPARQL_USERNAME")
    password = getenv("SPARQL_PASSWORD")
    endpoint = getenv("SPARQL_ENDPOINT")

    assert endpoint, f"Missing SPARQL_ENDPOINT"
    assert not username or username and password, "Missing SPARQL_PASSWORD"

    store = SPARQLStore(
        query_endpoint=endpoint,
        auth=(username, password) if username and password else None,
        method="POST_FORM",
        returnFormat="json",
        headers={"User-Agent": get_user_agent_header()},
    )

    return store


@cache
def get_graph() -> Graph:
    """Retrieve the default graph from the store."""

    store = get_store()
    graph = Graph(store=store, bind_namespaces="none")

    return graph


@cache
def get_user_agent_header() -> str:
    """Construct the HTTP User-Agent header to use."""

    value = getenv("HTTP_USER_AGENT") or " ".join(
        (
            f"RDFGraphProxy/0.1 ({system()} {machine()})",
            f"RDFLib/{__version__}",
            f"{python_implementation()}/{python_version()}",
        )
    )

    return value


def get_document(uri: str) -> Graph:
    """Get the document graph for the specified URI."""

    store_graph = get_graph()
    document_uri = URIRef(uri.split("#")[0])
    document_graph = Graph(identifier=document_uri, bind_namespaces="rdflib")

    # Add custom prefixes so they show up in the serialisation
    for prefix, value in CUSTOM_PREFIXES.items():
        document_graph.namespace_manager.bind(prefix=prefix, namespace=value)

    # This would ideally NOT be done with string formatting, but through initBindings.
    # However, RDFLib initBindings places the VALUES clause outside SELECT, which does not work.
    result = store_graph.query(
        f"""SELECT DISTINCT ?resource WHERE {{
            ?resource ?p ?o .
            FILTER(
                (
                    (?resource = ?document) ||
                    STRSTARTS(STR(?resource), CONCAT(STR(?document), "#"))
                ) && ISIRI(?resource)
            )
            VALUES ?document {{ {document_graph.identifier.n3()} }}
        }}"""
    )

    for bindings in result.bindings:
        resource_uri = bindings.get(RESOURCE_VARIABLE)
        assert isinstance(
            resource_uri, URIRef
        ), f"Collected non-URI resource {resource_uri.n3() if resource_uri else resource_uri}"
        store_graph.cbd(resource=resource_uri, target_graph=document_graph)

    debug(f"Retrieved {len(document_graph)} quads for {document_graph.identifier.n3()}")

    if not document_graph:
        abort(HTTPStatus.NOT_FOUND.value)

    return document_graph
