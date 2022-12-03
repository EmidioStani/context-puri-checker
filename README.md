# context-puri-checker

Execute with command

This script is pytest suite that takes as input a set of json-ld context files (stored in the testdata directory) from which it extract all the uris and execute the following tests:

1) test_uri_not_found, for a URI starting with http://data.europa.eu/m8g/ it should redirect to https://semiceu.github.io/ (see configuration file) while other URI (considered external) should return a HTTP status code 200
2) test_duplicate_uri, to test if 2 properties in the json-ld coxtext have the same URI
3) test_rdf_not_found, to test the existene of the RDF expressions for each URI, the list of RDF expression is indicated in the configuration ifle.   

pytest .\tests\test.py -s --excelreport=report.xlsx