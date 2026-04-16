"""Functionality related to data access."""

from os import getenv
from re import sub
from http import HTTPStatus
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
from rdflib.graph import Dataset
from rdflib.namespace import NamespaceManager
from rdflib.plugins.stores.sparqlstore import SPARQLUpdateStore

from config import QUERY_ENDPOINT
from config import GRAPH_IDENTIFIER
from config import SPARQL_PASSWORD
from config import RDF_PREFIXES
from config import SPARQL_USERNAME
from config import UPDATE_ENDPOINT

VARIABLE_SUBJECT = Variable("s")
VARIABLE_PREDICATE = Variable("p")
VARIABLE_OBJECT = Variable("o")
DOCUMENT_VARIABLE = Variable("document")

# Collects all document members based on their IRI, except for blank nodes.
# This allows collecting all members with a single query.
CONSTRUCT_DOCUMENT_MEMBERS = sub(
    r"\s+",
    " ",
    """
    CONSTRUCT {
        ?s ?p ?o .
    } WHERE {
        ?s ?p ?o .

        FILTER(
            isIRI(?s) &&
            (
                (?s = ?document) ||
                STRSTARTS(STR(?s), CONCAT(STR(?document), "#"))
            )
        )

        VALUES ?document { ?document_uri }
    }
""",
)


@cache
def get_graph() -> Graph:
    """Retrieve the specified graph from the store."""

    store = SPARQLUpdateStore(
        query_endpoint=QUERY_ENDPOINT,
        update_endpoint=UPDATE_ENDPOINT,
        autocommit=False,
        context_aware=True,
        dirty_reads=False,
        postAsEncoded=False,
        auth=(
            (SPARQL_USERNAME, SPARQL_PASSWORD)
            if SPARQL_USERNAME and SPARQL_PASSWORD
            else None
        ),
        method="POST_FORM",
        # returnFormat="json",
        headers={"User-Agent": get_user_agent_header()},
    )

    assert GRAPH_IDENTIFIER, "Missing GRAPH_IDENTIFIER"

    dataset = Dataset(store=store, default_union=False)

    # Ensure there are no namespace bindings, because RDFLib serialises all of
    # them in the queries, whether they are found in the query or not...
    dataset.namespace_manager = NamespaceManager(graph=dataset, bind_namespaces="none")

    graph_identifier = URIRef(GRAPH_IDENTIFIER)

    if UPDATE_ENDPOINT:
        graph = dataset.graph(identifier=graph_identifier)
    else:
        graph = dataset.get_graph(identifier=graph_identifier)
        assert graph, f"Missing graph: {graph_identifier.n3()}"

    return graph


@cache
def get_user_agent_header() -> str:
    """Construct the HTTP User-Agent header to use."""

    value = getenv("USER_AGENT") or " ".join(
        (
            f"RDFProxy/0.1 ({system()}, {machine()})",
            f"RDFLib/{__version__}",
            f"{python_implementation()}/{python_version()}",
        )
    )

    debug(f"Using HTTP User-Agent: {value}")

    return value


def get_document(uri: str) -> Graph:
    """Get the document graph for the specified URI."""

    store_graph = get_graph()
    document_graph = Graph(identifier=uri, bind_namespaces="none")

    # This would ideally NOT be done with string replacement, but through
    # initBindings. RDFLib, however, places the VALUES clause outside the
    # WHERE clause, which breaks it.
    result = store_graph.query(
        query_object=CONSTRUCT_DOCUMENT_MEMBERS.replace(
            "?document_uri",
            document_graph.identifier.n3(),
        )
    )

    if result.graph:
        document_graph += result.graph
        debug(
            f"Retrieved {len(document_graph)} quads for {document_graph.identifier.n3()}"
        )

    if not document_graph:
        abort(HTTPStatus.NOT_FOUND.value)

    # Add custom prefixes so they show up in the serialisation
    for prefix, value in RDF_PREFIXES.items():
        document_graph.namespace_manager.bind(prefix=prefix, namespace=value)

    return document_graph
