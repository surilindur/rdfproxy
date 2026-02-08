from json import dumps
from pathlib import Path

from rdflib.graph import Graph

if __name__ == "__main__":
    graph = Graph(bind_namespaces="rdflib")
    path = Path(__file__).parent.joinpath("default_prefixes.json")
    data = {k: str(v) for k, v in graph.namespace_manager.namespaces()}
    with open(path, "w") as output_file:
        output_file.write(dumps(data, indent=2, sort_keys=True))
