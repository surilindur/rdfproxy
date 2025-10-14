<p align="center">
  <img alt="logo" src="./.github/assets/logo.svg" width="64">
</p>

<p align="center">
  <a href="https://github.com/surilindur/rdfdp/actions/workflows/ci.yml"><img alt="CI" src=https://github.com/surilindur/rdfdp/actions/workflows/ci.yml/badge.svg?branch=main"></a>
  <a href="https://www.python.org/"><img alt="Python" src="https://img.shields.io/badge/%3C%2F%3E-Python-%233776ab.svg"></a>
  <a href="https://github.com/psf/black"><img alt="Code style: black" src="https://img.shields.io/badge/Code%20Style-black-000000.svg"></a>
  <a href="https://opensource.org/licenses/MIT"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-%23750014.svg"></a>
</p>

Experimental simple Flask application to serve resources from local documents with content negotiation.
Everything is declared in RDF, including static assets, to enable content negotiation over all resources.

The application performs the following during startup:

1. All the data from local RDF documents is loaded into an in-memory dataset.
2. All the queries are executed as update queries on this in-memory dataset.
3. VoID dataset descriptions are generated for each unique hostname, treating the hostname root URI as the dataset.

Upon receiving a request, the application does the following:

1. Finds the corresponding resource URI from the in-memory dataset. If no resource is found, this is reported to the client.
2. Collects the Concise Bounded Description of every URI that would belong in the document URI, and treats this as the response data.
3. Performs content negotiation over this resource.
   If the document URI is declared as a `schema:MediaObject`, the application will prioritise the on-disk file mimetype over everything else.
   Other resources will perform normal content negotiation, but prefer `text/turtle` in case of missing client preference.
   When HTML is chosen as the format but there is no applicable template, a content negotiation error is reported.

## Dependencies

* Python
* [RDFLib](https://github.com/RDFLib/rdflib)
* [Flask](https://github.com/pallets/flask)
* [Mistune](https://github.com/lepture/mistune)

## Usage

The application can be configured using environment variables:

* `DATA_PATH`: The RDF data directory.
* `QUERIES_PATH`: The queries directory.
* `TEMPLATE_PATH`: The path to the templates directory.

The following HTTP proxy headers will be taken into consideration when identifying actual resource URIs:

* `X-Forwarded-Host`: Substituted for the host value when provided.
* `X-Forwarded-Proto`: Substituted for the protocol value when provided.

Further configuration is possible for Flask via [environment variables](https://flask.palletsprojects.com/en/stable/api/#flask.Config.from_prefixed_env).
For example, to set some options for [Flask](https://flask.palletsprojects.com/en/stable/config/):

* `FLASK_USE_X_SENDFILE=true` to use `X-Sendfile` header with a proxy server.

The following custom configuration options are available:

* `FLASK_USE_X_ACCEL_REDIRECT`, to return static files as empty responses with the `X-Accel-Redirect` set to the on-disk file path. This requires additional server configuration, and is experimental.

## Resources

The resources are defined in RDF, with static assets declared as `schema:MediaObject` with their on-disk file URIs.
Only the resources defined in RDF are served by the proxy, under their defined URIs.
The URI of the resource definitions must match the public exposed URIs of the application.
For examples, see the definitions in the [example](./example/) directory.

## Templates

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
