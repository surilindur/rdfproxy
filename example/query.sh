#!/bin/bash

query='SELECT DISTINCT ?resource WHERE {
    ?resource ?p ?o .
    FILTER(
        (
            (?resource = ?document) ||
            STRSTARTS(STR(?resource), CONCAT(STR(?document), "#"))
        ) && ISIRI(?resource)
    )
    VALUES (?document) {
        (<http://localhost:5000/>)
    }
}'

endpoint=http://localhost:3030/example/sparql

curl --header "Content-Type: application/sparql-query" --data "$query" "$endpoint"
