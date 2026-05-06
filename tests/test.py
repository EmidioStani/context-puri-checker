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
from collections import defaultdict

import re 
import phunspell
pspell_en = phunspell.Phunspell('en_GB')

def check_mispell(definition: str) -> None:
    """    
    Checks a definition for any misspelled words using French and English dictionaries.    
    
    This function uses a regular expression to split the definition into words, filtering out punctuation and whitespace. It checks for spelling errors first against a French dictionary, then against an English dictionary.    
    
    Parameters:    
    -----------    
    definition : str    
        The text definition to be checked for spelling errors.    
    
    Returns:    
    --------    
    None    
    
    Side Effects:    
    -------------    
    - Logs any misspelled words found in the definition to the console.    
    """ 
    b = config['spell']['separators']
    acronyms = config['spell']['acronyms']
    escaped_separators = list(map(re.escape, b))  
    
    # Construct the regex pattern  
    pattern = r'(' + '|'.join(escaped_separators) + r'|\s+)'

    res = list(filter(None, re.split(pattern, definition)))
    result = list(set(res) - set(b) - set(acronyms))
    mispelled_en = pspell_en.lookup_list(result)
    return mispelled_en


def get_config(file):
    my_path = Path(__file__).resolve()
    config_path = my_path.parent / file
    with config_path.open(encoding="utf-8") as config_file:
        config = yaml.load(config_file, Loader=yaml.FullLoader)
    return config

config = get_config("config.yaml")
folder = config['input']['folder']

tool = language_tool_python.LanguageTool('en-US')

def removeDuplicates(lst):
    return list(set([i for i in lst]))

def expand_uri(uri_ref, namespaces):
    """
    Expand a prefixed URI reference to a full URI.
    
    Parameters:
    -----------
    uri_ref : str
        The URI reference (e.g., "tree:shape" or "https://example.com/resource")
    namespaces : dict
        Dictionary of namespace prefixes to full namespace URIs
    
    Returns:
    --------
    str
        The expanded URI
    """
    if uri_ref.startswith(('http://', 'https://', 'urn:')):
        # Already a full URI
        return uri_ref
    
    if ':' in uri_ref:
        prefix, local_name = uri_ref.split(':', 1)
        if prefix in namespaces:
            return namespaces[prefix] + local_name
    
    return uri_ref


def extract_namespaces(context_data):
    """
    Extract namespace definitions from the JSON-LD context.
    
    Parameters:
    -----------
    context_data : dict
        The @context dictionary
    
    Returns:
    --------
    dict
        Dictionary mapping prefixes to namespace URIs
    """
    namespaces = {}
    for key, value in context_data.items():
        if isinstance(value, str) and (value.startswith(('http://', 'https://', 'urn:'))):
            # This is a namespace definition
            namespaces[key] = value
    return namespaces


def read_test_data_from_context(data, namespaces):
    """
    Extract URIs from context data, expanding prefixed URIs using namespaces.
    
    Parameters:
    -----------
    data : dict
        The @context dictionary
    namespaces : dict
        Namespace prefix mappings
    
    Returns:
    --------
    list
        List of tuples (key, expanded_uri)
    """
    test_data = []
    
    for k, v in data.items():
        if isinstance(v, str):
            # Direct URI or prefixed reference
            expanded_uri = expand_uri(v, namespaces)
            test_data.append(tuple([k, expanded_uri]))
        elif isinstance(v, dict):
            # Complex definition with @id, @type, @container, etc.
            if '@id' in v:
                expanded_uri = expand_uri(v['@id'], namespaces)
                test_data.append(tuple([k, expanded_uri]))
    
    return test_data


def read_files(folder):
    """
    Read all JSON files in folder and extract URI definitions.
    
    Parameters:
    -----------
    folder : str
        Path to folder containing JSON-LD files
    
    Returns:
    --------
    list
        List of tuples (label, expanded_uri)
    """
    data_files = []
    
    for filename in os.listdir(folder):
        filepath = os.path.join(folder, filename)
        # checking if it is a file
        if os.path.isfile(filepath):
            try:
                file = open(filepath)
                data = json.load(file)['@context']
                
                # Extract namespaces first
                namespaces = extract_namespaces(data)
                
                # Extract all URIs with namespace expansion
                temp_file_list = read_test_data_from_context(data, namespaces)
                data_files.extend(temp_file_list)
                file.close()
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Error processing file {filepath}: {e}")
                continue
    
    data_files = removeDuplicates(data_files)
    return data_files


def uri_in_data(list, uri):
    list_tuple_containing_uri = []
    for k, v in list:
        if (v == uri):
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
                    skip_link = True
                else:
                    skip_link = False
                    if(a_link.startswith(".")):
                        a_link = spec + a_link[2:]
                    if(a_link.startswith("/")):
                        a_link = "https://semiceu.github.io/" + a_link[1:]
                if (not skip_link):
                    spec_links.append(a_link)
        spec_links = removeDuplicates(spec_links)
    return spec_links


def read_texts():
    """
    Extract text content from specification pages for spell-checking.
    
    Returns:
    --------
    list
        List of text sections extracted from spec pages
    """
    spec_texts = []
    
    for spec in get_specs():
        try:
            html_page = urllib.request.urlopen(spec)
            soup = BeautifulSoup(html_page, "html.parser")
            
            # Try multiple tag types: section, article, div with class content, main
            tag_selectors = [
                ('section', {}),
                ('article', {}),
                ('main', {}),
                ('div', {'class': ['content', 'main', 'doc', 'body']}),
            ]
            
            found_text = False
            for tag_name, attrs in tag_selectors:
                if attrs:
                    # Search for tag with specific attributes
                    tags = soup.find_all(tag_name, class_=attrs.get('class'))
                else:
                    # Search for tag without attribute constraints
                    tags = soup.find_all(tag_name)
                
                for tag in tags:
                    text_content = tag.get_text()
                    if text_content.strip():  # Only add non-empty text
                        strip_section = " ".join(
                            (text_content.strip()
                             .replace("\n", " ")
                             .replace("\t", " ")
                             .replace("\r", " "))
                            .split()
                        )
                        if strip_section:  # Only add if not empty after cleaning
                            spec_texts.append(strip_section)
                            found_text = True
                
                if found_text:
                    break
            
            # Fallback: if no text found with tags, extract all body text
            if not found_text:
                body_text = soup.get_text()
                if body_text.strip():
                    strip_section = " ".join(
                        (body_text.strip()
                         .replace("\n", " ")
                         .replace("\t", " ")
                         .replace("\r", " "))
                        .split()
                    )
                    if strip_section:
                        spec_texts.append(strip_section)
                        print(f"Warning: No structured tags found in {spec}, using full body text")
        
        except Exception as e:
            print(f"Error processing spec {spec}: {e}")
            continue
    
    return spec_texts


# @pytest.mark.skip(reason="excluded for now")
@pytest.mark.parametrize("label, uri", read_files(folder))
def test_uri_not_found(label, uri):
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    response = requests.get(uri, headers=headers, verify=False, allow_redirects=True)
    
    # Accept 200 status code
    assert response.status_code == 200, (
        f"URI {uri} returned status {response.status_code}. "
        f"Final URL: {response.url}"
    )
    
    # Check for expected redirects if configured
    if (uri.startswith(config['input']['namespace']['m8g'])):
        assert response.url.startswith(config['input']['namespace']['fwd']), (
            f"m8g URI {uri} did not redirect to expected namespace. "
            f"Original URI: {uri}\n"
            f"Final URL: {response.url}\n"
            f"Expected to start with: {config['input']['namespace']['fwd']}"
        )


def group_by_uri(data):
    grouped = defaultdict(list)
    for label, uri in data:
        grouped[uri].append(label)
    return grouped


uris_with_labels = list(group_by_uri(read_files(folder)).items())

# @pytest.mark.skip(reason="excluded for now")
@pytest.mark.parametrize("uri, labels", 
                         uris_with_labels, 
                         ids=[uri for uri, _ in uris_with_labels])
def test_duplicate_uri(uri, labels):
    assert len(labels) <= 1, (
        f"Duplicate URI found: {uri}\n"
        f"Used by labels: {labels}"
    )


# @pytest.mark.skip(reason="excluded for now")
@pytest.mark.parametrize("label, uri",  read_m8g_data_from_context(folder))
@pytest.mark.parametrize("response_type",  get_supported_response_types())
def test_rdf_not_found(label, uri, response_type):
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
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Encoding" : "gzip, deflate, br, zstd",
        "Accept-Language" : "en-GB,en-US;q=0.9,en;q=0.8",
        "Cache-Control" : "no-cache",
        "User-Agent" : "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0"
    }
    response = requests.get(url, headers=headers, verify=False)
    assert response.status_code == 200


@pytest.mark.parametrize("url", read_specs())
def test_url_not_good(url):
    result = 0
    if ("http://fixme.com" in url):
        result = 1
    assert result == 0

MAX_ID_LEN = 100  # characters to show before cutting

def short_id(text: str) -> str:
    """Return a safe pytest ID by truncating long text values."""
    clean = text.replace("\n", " ").replace("\r", " ").strip()
    if len(clean) > MAX_ID_LEN:
        clean = clean[:MAX_ID_LEN - 3] + "..."
    return clean

@pytest.mark.parametrize("text", read_texts(), ids=short_id)
def test_text_not_good(text):
    n_matches = 0
    matches = check_mispell(text)
    n_matches = len(matches)
    assert n_matches == 0, f"Language errors: {matches}"