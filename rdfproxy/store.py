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
from rdflib.term import BNode
from rdflib.term import Literal
from rdflib.term import Variable
from rdflib.graph import Graph
from rdflib.graph import Dataset
from rdflib.namespace import NamespaceManager
from rdflib.plugins.stores.sparqlstore import SPARQLStore

from config import SPARQL_ENDPOINT
from config import SPARQL_GRAPH
from config import SPARQL_PASSWORD
from config import RDF_PREFIXES
from config import SPARQL_USERNAME

VARIABLE_SUBJECT = Variable("s")
VARIABLE_PREDICATE = Variable("p")
VARIABLE_OBJECT = Variable("o")

# Collects the Concise Bounded Description for ?document_uri, but with blank
# nodes collected only over one hop - otherwise the query count could explode.
ONE_HOP_CBD_QUERY = sub(
    r"\s+",
    " ",
    """
    SELECT DISTINCT ?s ?p ?o WHERE
    {
        ?s ?p ?o .

        FILTER(
            (
                isIRI(?s) &&
                ( (?s = ?document) || STRSTARTS(STR(?s), CONCAT(STR(?document), "#")) )
            ) ||
            ( isBlank(?s) && EXISTS { ?document ?hop ?s } )
        )

        VALUES ?document { ?document_uri }
    }
""",
)


@cache
def get_graph() -> Graph:
    """Retrieve the specified graph from the store."""

    store = SPARQLStore(
        query_endpoint=SPARQL_ENDPOINT,
        auth=(
            (SPARQL_USERNAME, SPARQL_PASSWORD)
            if SPARQL_USERNAME and SPARQL_PASSWORD
            else None
        ),
        method="POST_FORM",
        returnFormat="json",
        headers={"User-Agent": get_user_agent_header()},
        context_aware=True,
    )

    if SPARQL_GRAPH:
        dataset = Dataset(store=store, default_union=False)
        graph = dataset.graph(identifier=SPARQL_GRAPH)
    else:
        graph = Graph(store=store)

    # Ensure there are no namespace bindings, because RDFLib serialises all of
    # them in the queries, whether they are found in the query or not...
    graph.namespace_manager = NamespaceManager(graph=graph, bind_namespaces="none")

    return graph


@cache
def get_user_agent_header() -> str:
    """Construct the HTTP User-Agent header to use."""

    value = getenv("HTTP_USER_AGENT") or " ".join(
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
    document_uri = URIRef(uri.split("#")[0])
    document_graph = Graph(identifier=document_uri, bind_namespaces="none")

    # This would ideally NOT be done with string formatting, but through initBindings.
    # However, RDFLib initBindings places the VALUES clause outside SELECT...
    query = ONE_HOP_CBD_QUERY.replace("?document_uri", document_uri.n3())
    result = store_graph.query(query)

    # Add custom prefixes so they show up in the serialisation
    for prefix, value in RDF_PREFIXES.items():
        document_graph.namespace_manager.bind(prefix=prefix, namespace=value)

    for bindings in result.bindings:
        value_s = bindings.get(VARIABLE_SUBJECT)
        value_p = bindings.get(VARIABLE_PREDICATE)
        value_o = bindings.get(VARIABLE_OBJECT)
        assert isinstance(value_s, (URIRef, BNode)), f"Bad subject: {value_s}"
        assert isinstance(value_p, URIRef), f"Bad predicate: {value_p}"
        assert isinstance(value_o, (Literal, URIRef, BNode)), f"Bad object: {value_o}"
        document_graph.add((value_s, value_p, value_o))

    debug(f"Retrieved {len(document_graph)} quads for {document_graph.identifier.n3()}")

    if not document_graph:
        abort(HTTPStatus.NOT_FOUND.value)

    return document_graph
