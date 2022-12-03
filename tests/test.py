import json
import os
from distutils import filelist
from pathlib import Path

import pytest
import requests
import yaml
from rdflib import Graph


def get_config(file):
    my_path = Path(__file__).resolve()  # resolve to get rid of any symlinks
    config_path = my_path.parent / file
    with config_path.open() as config_file:
        config = yaml.load(config_file, Loader=yaml.FullLoader)
    return config

config = get_config("config.yaml")
folder = config['input']['folder']

def removeDuplicates(lst):
    return list(set([i for i in lst]))

def read_test_data_from_context(data):
    test_data = []
    #print(data)
    for k, v in data.items():
        if(isinstance(v, str)):
            test_data.append(tuple([k,v]))
        else:
            if(isinstance(v, dict)):
                test_data.append(tuple([k,v['@id']]))
    return test_data

def read_files(folder):
    data_files = []
    for filename in os.listdir(folder):
        filepath = os.path.join(folder, filename)
        # checking if it is a file
        if os.path.isfile(filepath):
            # print("reading: " + filepath)
            file = open(filepath)
            data = json.load(file)['@context']
            temp_file_list = read_test_data_from_context(data)
            data_files.extend(temp_file_list)
            file.close()
    # print(data_files)
    data_files =  removeDuplicates(data_files)
    # print("removing")
    # print(data_files)   
    return data_files

def uri_in_data(list, uri):
    list_tuple_containing_uri = []
    for k, v in list:
        if (v == uri):
            # print(v)
            list_tuple_containing_uri.append(tuple([k,v]))
    if(len(list_tuple_containing_uri) > 1):
        return 1
    else:
        return 0


def read_m8g_data_from_context(folder):
    data = read_files(folder)
    namespace = config['input']['namespace']['m8g']
    test_data = []
    for index, tuple in enumerate(data):
        k = tuple[0]
        v = tuple[1]
        if v.startswith(namespace):
            test_data.append(tuple)
    # print("found")
    # print(test_data)
    return test_data

def get_supported_response_types():
    return config['response']['types']

# read_m8g_data_from_context(folder)

@pytest.mark.parametrize("label, uri", read_files(folder))
def test_uri_not_found(label, uri):
    response = requests.get(uri)
    # print(response.history)
    # print(response.status_code)
    if (uri.startswith(config['input']['namespace']['m8g'])):
        assert response.url.startswith(config['input']['namespace']['fwd'])
    else:
        assert response.status_code == 200

@pytest.mark.parametrize("label, uri", read_files(folder))
def test_duplicate_uri(label, uri):
    is_uri_used = uri_in_data(read_files(folder), uri)
    assert is_uri_used == 0

@pytest.mark.parametrize("label, uri",  read_m8g_data_from_context(folder))
@pytest.mark.parametrize("response_type",  get_supported_response_types())
def test_rdf_not_found(label, uri, response_type):
    print("check " + uri)
    headers = {'Accept': response_type}
    response = requests.get(uri, headers=headers)
    assert response.status_code == 200
    content_type = response.headers['Content-Type']
    assert content_type.startswith(response_type)
    g = Graph()
    g.parse(response.content, format=response_type)
    for s, p, o in g.triples((None, None, None)):
        assert str(s) == uri

