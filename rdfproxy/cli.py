"""Helper script to publish RDF data using SPARQL UPDATE."""

from logging import debug
from logging import info
from logging import warning
from pathlib import Path
from argparse import ArgumentParser
from argparse import Namespace
from argparse import BooleanOptionalAction

from config import RDF_EXTENSIONS
from config import QUERY_EXTENSIONS
from store import get_graph
from utils import iterate_by_extension


class RDFUpdateNamespace(Namespace):  # pylint: disable=too-few-public-methods
    """Argument definition."""

    erase: bool
    data: Path
    queries: Path | None
    debug: bool


def parse_args() -> type[RDFUpdateNamespace]:
    """Helper function to parse command line arguments."""

    parser = ArgumentParser(
        description="Helper script to publish RDF data using SPARQL UPDATE queries.",
    )

    parser.add_argument(
        "--data",
        type=lambda p: Path(p).resolve(strict=True),
        required=True,
        help="Path containing local RDF files to be published.",
    )

    parser.add_argument(
        "--queries",
        type=lambda p: Path(p).resolve(strict=True),
        required=False,
        help="Path containing local SPARQL query files to execute after publishing.",
    )

    parser.add_argument(
        "--erase",
        action=BooleanOptionalAction,
        default=False,
        help="Clears the target graph before publishing new data.",
    )

    args = parser.parse_args(namespace=RDFUpdateNamespace)

    return args


def publish_data(args: type[RDFUpdateNamespace]) -> None:
    """Publish all data and execute queries after publishing."""

    graph = get_graph()

    info(f"Graph {graph.identifier.n3()} currently has {len(graph)} triples")

    if args.erase:
        warning("Erasing target graph")
        graph.update("DELETE WHERE { ?s ?p ?o }")

    for fp in iterate_by_extension(path=args.data, extensions=RDF_EXTENSIONS):
        debug(f"Parsing {fp}")
        graph.parse(source=fp)

    info(f"Graph {graph.identifier.n3()} has {len(graph)} triples after publishing")

    if args.queries:
        for fp in sorted(
            iterate_by_extension(path=args.queries, extensions=QUERY_EXTENSIONS),
            key=lambda p: p.name,
        ):
            debug(f"Executing {fp}")
            with open(fp, "r", encoding="utf-8") as query_file:
                graph.update(query_file.read())

        info(f"Graph {graph.identifier.n3()} has {len(graph)} triples after queries")

    graph.commit()


def main() -> None:
    """The main function."""

    args = parse_args()
    publish_data(args=args)


if __name__ == "__main__":
    main()
