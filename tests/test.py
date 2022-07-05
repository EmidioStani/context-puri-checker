import json
from distutils import filelist
from pathlib import Path

import pytest
import requests
import yaml
from rdflib import Graph


def get_config(file):
    with open(file, 'r') as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
    return config

config = get_config("testdata/config.yaml")
file = config['input']['file']
f = open("testdata/" + file)
print(f)
data = json.load(f)['@context']

def read_test_data_from_context(data):
    test_data = []
    for k, v in data.items():
        if(isinstance(v, str)):
            test_data.append(tuple([k,v]))
        else:
            if(isinstance(v, dict)):
                test_data.append(tuple([k,v['@id']]))
    return test_data

def read_m8g_data_from_context(data):
    namespace = config['input']['namespace']['m8g']
    test_data = []
    for k, v in data.items():
        if(isinstance(v, str)):
            if v.startswith(namespace):
                test_data.append(tuple([k,v]))
        else:
            if(isinstance(v, dict)):
                if v['@id'].startswith(namespace):
                    test_data.append(tuple([k,v['@id']]))
    return test_data

def get_supported_response_types():
    return config['response']['types']

@pytest.mark.parametrize("label, uri",  read_test_data_from_context(data))
def test_using_data_from_context(label, uri):
    response = requests.get(uri)
    assert response.status_code == 200

@pytest.mark.parametrize("label, uri",  read_m8g_data_from_context(data))
@pytest.mark.parametrize("response_type",  get_supported_response_types())
def test_using_data_from_context_rdf(label, uri, response_type):
    headers = {'Accept': response_type}
    response = requests.get(uri, headers=headers)
    assert response.status_code == 200
    content_type = response.headers['Content-Type']
    assert content_type.startswith(response_type)
    g = Graph()
    g.parse(response.content, format=response_type)
    for s, p, o in g.triples((None, None, None)):
        assert str(s) == uri

f.close()
