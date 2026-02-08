<p align="center">
  <strong>RDF Graph Proxy</strong>
</p>

<p align="center">
  <a href="https://github.com/surilindur/rdfgp/actions/workflows/ci.yml">
    <img alt="CI" src=https://github.com/surilindur/rdfgp/actions/workflows/ci.yml/badge.svg?branch=main">
  </a>
  <a href="https://www.python.org/">
    <img alt="Python" src="https://img.shields.io/badge/%3C%2F%3E-Python-%233776ab.svg">
  </a>
  <a href="https://github.com/psf/black">
    <img alt="Code style: black" src="https://img.shields.io/badge/Code%20Style-black-000000.svg">
  </a>
  <a href="https://opensource.org/licenses/MIT">
    <img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-%23750014.svg">
  </a>
</p>

This is a proof-of-concept prototype implementation of an [RDF](https://www.w3.org/TR/rdf12-concepts/) resource proxy,
that serves client-preferred serialisations from a [SPARQL endpoint](https://www.w3.org/TR/sparql12-protocol/)
based on HTTP [content negotiation](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Content_negotiation).

## Resource mapping approach

The application maps resources URIs to documents followind the usual convention,
where a fragment identifier is assumed to be part of the document URI to which the fragment is appended.
For every resources identified as part of the requested document,
the application collects the [Concise Bounded Description](https://www.w3.org/submissions/CBD/),
and returns a serialisation containing all of these descriptions.

## Proxy server support

The following HTTP proxy headers will be taken into consideration when identifying actual resource URIs:

* `X-Forwarded-Host`: Substituted for the host value when provided.
* `X-Forwarded-Proto`: Substituted for the protocol value when provided.

## Dependencies

* [Python](https://www.python.org/)
* [RDFLib](https://github.com/RDFLib/rdflib)
* [Flask](https://github.com/pallets/flask)

## Configuration options

The following environment variables are used to configure the data source,
and are passed on to RDFLib's `SPARQLStore`:

* `SPARQL_ENDPOINT`: The endpoint URI, passed to RDFLib
* `SPARQL_USERNAME`: The username to use (optional)
* `SPARQL_PASSWORD`: The password to use (optional)

The following options exist for configuring the application itself:

* `TEMPLATE_PATH`: The path to HTML templates, defaults to `/usr/share/rdfgpp`

Additionally, the Flask application configuration is [loaded from prefixed environment variables](https://flask.palletsprojects.com/en/stable/config/#configuring-from-environment-variables).

## Template mapping and context

The template is selected based on the types of the document URI.
For example, if the document URI is declared as having `rdf:type` of `schema:BlogPosting`, then `BlogPosting.html` is selected as the template.
The fallback error template name is `_error.html`, and HTTP status code errors use templates such as `_500.html`.

The following variables are made available to the templates:

* Current year as `current_year`
* Current document graph as `document_graph`
* Current document URI as `document_uri`
* Current type name used to select template as `template_type` unless using the default template
* Current debug mode flag as `app_debug`

For error pages, the following variables are available:

* Current error code as `error_code`
* Current error title as `error_title`
* Current error description as `error_description`
* Current error message as `error_message`

The following filters are available to the templates:

* Markdown-to-HTML conversion function as `markdown_to_html`
* Predicate value-based subject sorting function as `sort_by_predicate`

## Issues

Please feel free to report any issues on the GitHub issue tracker.

## License

This code is copyrighted and released under the [MIT license](http://opensource.org/licenses/MIT).
