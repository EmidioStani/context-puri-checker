import json
import os
from distutils import filelist
from pathlib import Path

import pytest
import requests
import yaml
from rdflib import Graph

from bs4 import BeautifulSoup
import urllib.request

import language_tool_python


def get_config(file):
    my_path = Path(__file__).resolve()  # resolve to get rid of any symlinks
    config_path = my_path.parent / file
    with config_path.open() as config_file:
        config = yaml.load(config_file, Loader=yaml.FullLoader)
    return config

config = get_config("config.yaml")
folder = config['input']['folder']

tool = language_tool_python.LanguageTool('en-US')

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

def get_specs():
    return config['input']['specs']

def read_specs():
    spec_links = []
    skip_link = False
    for spec in get_specs():
        html_page = urllib.request.urlopen(spec)
        soup = BeautifulSoup(html_page, "html.parser")
        for link in soup.findAll('a'):
            a_link = ""
            a_link = link.get('href')
            if(a_link is not None):
                if(a_link.startswith("#") or "/issues/new?title=Issue%20" in a_link):
                    # print("skip check " + a_link)
                    skip_link = True
                else:
                    skip_link = False
                    if(a_link.startswith(".")):
                        a_link = spec + a_link[2:]
                        # print("concat check " + a_link)
                    if(a_link.startswith("/")):
                        a_link = "https://semiceu.github.io/" + a_link[1:]
                        # print("concat check " + a_link)
                if (not skip_link):
                    spec_links.append(a_link)
        spec_links =  removeDuplicates(spec_links)
    return spec_links

def read_texts():
    spec_texts = []
    skip_link = False
    for spec in get_specs():
        html_page = urllib.request.urlopen(spec)
        soup = BeautifulSoup(html_page, "html.parser")
        for section_tag in soup.find_all('section'):
            strip_section = " ".join( ((section_tag.text).strip().replace("\n"," ").replace("\t"," ").replace("\r"," ")).split() )
            spec_texts.append(strip_section)
    return spec_texts

@pytest.mark.parametrize("label, uri", read_files(folder))
def test_uri_not_found(label, uri):
    response = requests.get(uri,  verify=False)
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
    # print("check " + uri)
    headers = {'Accept': response_type}
    response = requests.get(uri, headers=headers, verify=False)
    assert response.status_code == 200
    content_type = response.headers['Content-Type']
    assert content_type.startswith(response_type)
    g = Graph()
    g.parse(response.content, format=response_type)
    for s, p, o in g.triples((None, None, None)):
        assert str(s) == uri

@pytest.mark.parametrize("url", read_specs())
def test_hyperlink_not_found(url):
    # print("check " + url)
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Encoding" : "gzip, deflate, br, zstd",
        "Accept-Language" : "en-GB,en-US;q=0.9,en;q=0.8",
        "Cache-Control" : "no-cache",
        "User-Agent" : "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0"
    }
    response = requests.get(url, headers=headers, verify=False)
    # print(response.history)
    # print(response.status_code)
    assert response.status_code == 200

@pytest.mark.parametrize("url", read_specs())
def test_url_not_good(url):
    result = 0
    # print("check " + url)
    if ("http://fixme.com" in url):
        result = 1
    assert result == 0

@pytest.mark.skip(reason="excluded for now")
@pytest.mark.parametrize("text", read_texts())
def test_text_not_good(text):
    n_matches = 0
    # print("check " + url)
    tool = language_tool_python.LanguageTool('en-GB')
    matches = tool.check(text)
    n_matches = len(matches)
    tool.close()
    assert n_matches == 0, f"Language errors: {matches}"

