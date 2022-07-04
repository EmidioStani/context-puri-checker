from pathlib import Path

import pytest
import requests
import yaml


def get_config(file):
    my_path = Path(__file__).resolve()  # resolve to get rid of any symlinks
    config_path = my_path.parent / file
    with config_path.open() as config_file:
        config = yaml.load(config_file, Loader=yaml.FullLoader)
    return config



config = get_config("config.yaml")

file = config['input']['file']


ns1 = Namespace(config["namespaces"]["shacl"])
for s, p, o in g.triples((None, RDF.type, ns1.NodeShape)):
    start = config['input']['shapestart']
    end = config['input']['shapeend']
    worksheet_name = ((s.split(start))[1].split(end)[0]).replace(":","_")
    worksheet = workbook.add_worksheet(worksheet_name)
    
    for prefix, namespace in config["namespaces"].items():
        g.bind(prefix, Namespace(namespace))

    cell_format = workbook.add_format()
    cell_format.set_bold()

    worksheet.write('A1', config['output']['classuri'], cell_format)
    for ns, tc, cl in g.triples((s, ns1.targetClass, None)):
        worksheet.write('B1', str(cl))

    num_namespaces = len(config["namespaces"])
    for index, i in enumerate(config["namespaces"].items()):
        worksheet.write(index+1, 0, config['output']['prefix'] , cell_format)
        worksheet.write(index+1, 1, i[0])
        worksheet.write(index+1, 2, i[1])

    # worksheet.write(num_namespaces + 1, 0, config['output']['rdftype'], cell_format)
    # worksheet.write(num_namespaces + 1, 1, config['output']['rdfclass'])

    cell_format2 = workbook.add_format()
    cell_format2.set_bold()
    cell_format2.set_bg_color(config['output']['line']['bgcolor'])

    propertiesrow = num_namespaces + 2
    worksheet.write(propertiesrow, 0, config['output']['line']['URI'], cell_format2)
    worksheet.write(propertiesrow, 1, config['output']['line']['type'], cell_format2)
    mylist = []
    mylist2 = []
    for a, b, c in g.triples((s, ns1.property, None)):
        for d, e, f in g.triples((c, ns1.path, None)):
            # print(f)
            property = URIRef(f)
            mylist.append(property.n3(g.namespace_manager))
        
        for d, e, f in g.triples((c, None, None)):
            if e == ns1.datatype:
                mylist2.append(f)
            if e == ns1['class']:
                mylist2.append("uri")
    print(mylist2)
    mylist3 = []
    for index, i in enumerate(mylist):
        if (mylist2[index] == URIRef(config['output']['line']['datatypes']['langString']['namespace'])):
            element = i + config['output']['line']['datatypes']['langString']['suffix']
            mylist3.append(element)
        else:
            mylist3.append(i)
    worksheet.write_row(propertiesrow, 2, mylist3, cell_format2)
    num_columns = 3 + len(mylist)
    for i in range(num_columns):
        set_column_autowidth(worksheet, i, 1.15)

workbook.close()
