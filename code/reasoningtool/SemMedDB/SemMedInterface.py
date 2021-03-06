__author__ = 'Finn Womack'
__copyright__ = 'Oregon State University'
__credits__ = ['Finn Womack']
__license__ = 'MIT'
__version__ = '0.1.0'
__maintainer__ = ''
__email__ = ''
__status__ = 'Prototype'

import sys
import os
new_path = os.path.join(os.getcwd(), '..', 'kg-construction')
sys.path.insert(0, new_path)

from QuerySemMedDB import QuerySemMedDB
from QueryUMLSSQL import QueryUMLSSQL
from QueryMyGene import QueryMyGene
from QueryMyChem import QueryMyChem
from QueryUMLSApi import QueryUMLS
import requests
import pandas
import time
import requests_cache
import numpy
import urllib
import ast

numpy.random.seed(int(time.time()))

requests_cache.install_cache('SemMedCache')

sys.path.append(os.path.dirname(os.path.abspath(__file__))+"/../../")  # code directory
from RTXConfiguration import RTXConfiguration

class SemMedInterface():

    def __init__(self, mapfile = 'node_cui_map.csv', mysql_timeout = 30):
        # self.smdb = QuerySemMedDB("rtxdev.saramsey.org",3306,"rtx_read","rtxd3vT3amXray","semmeddb", mysql_timeout)
        # self.umls = QueryUMLSSQL("rtxdev.saramsey.org",3406, "rtx_read","rtxd3vT3amXray","umls")
        rtxConfig = RTXConfiguration()
        self.smdb = QuerySemMedDB(rtxConfig.mysql_semmeddb_host, rtxConfig.mysql_semmeddb_port, rtxConfig.mysql_semmeddb_username, rtxConfig.mysql_semmeddb_password, "semmeddb", mysql_timeout)
        self.umls = QueryUMLSSQL(rtxConfig.mysql_umls_host, rtxConfig.mysql_umls_port, rtxConfig.mysql_umls_username, rtxConfig.mysql_umls_password, "umls")
        self.semrep_url = "http://rtxdev.saramsey.org:5000/semrep/convert?string="
        self.timeout_sec = 120
        self.mg = QueryMyGene()
        try:
            df = pandas.read_csv(mapfile, converters={'cuis':ast.literal_eval})
            cui_dict = {}
            if 'cuis' in df.columns and 'id' in df.columns:
                for a in range(len(df)):
                    for df_cui in df['cuis'][a]:
                        if df_cui in cui_dict.keys():
                            cui_dict[df_cui] += [df['id'][a]]
                        else:
                            cui_dict[df_cui] = [df['id'][a]]
                self.map_df = df
            self.cui_dict = cui_dict
        except FileNotFoundError:
            self.cui_dict = {}

    def send_query_get(self, url, retmax = 1000):
        url_str = url + '&retmax=' + str(retmax)
#        print(url_str)
        try:
            res = requests.get(url_str, headers={'accept': 'application/json'}, timeout=self.timeout_sec)
        except requests.exceptions.Timeout:
            print('HTTP timeout in SemMedInterface.py; URL: ' + url_str, file=sys.stderr)
            time.sleep(1)  ## take a timeout because NCBI rate-limits connections
            return None
        except requests.exceptions.ConnectionError:
            print('HTTP connection error in SemMedInterface.py; URL: ' + url_str, file=sys.stderr)
            time.sleep(1)  ## take a timeout because NCBI rate-limits connections
            return None
        status_code = res.status_code
        if status_code != 200:
            print('HTTP response status code: ' + str(status_code) + ' for URL:\n' + url_str, file=sys.stderr)
            res = None
        return res

    def query_oxo(self, uid):
        '''
        This takes a curie id and send that id to EMBL-EBI OXO to convert to cui
        '''
        url_str =  'https://www.ebi.ac.uk/spot/oxo/api/mappings?fromId=' + str(uid)
        try:
            res = requests.get(url_str, headers={'accept': 'application/json'}, timeout=self.timeout_sec)
        except requests.exceptions.Timeout:
            print('HTTP timeout in SemMedInterface.py; URL: ' + url_str, file=sys.stderr)
            time.sleep(1)  ## take a timeout because NCBI rate-limits connections
            return None
        except requests.exceptions.ConnectionError:
            print('HTTP connection error in SemMedInterface.py; URL: ' + url_str, file=sys.stderr)
            time.sleep(1)  ## take a timeout because NCBI rate-limits connections
            return None
        status_code = res.status_code
        if status_code != 200:
            print('HTTP response status code: ' + str(status_code) + ' for URL:\n' + url_str, file=sys.stderr)
            res = None
        return res

    def QuerySemRep(self, string):
        '''
        This takes a string and extracts cuis from it using SemRep (what SemMedDB uses to extract relationships from pubmed articles)
        '''
        url = self.semrep_url + str(string)
        res = self.send_query_get(url)
        if res is None:
            return None
        elif res.status_code == 200:
            data = res.json()
            return data
        else:
            return None

    def get_cui_from_umls(self, curie_id, mesh_flag = False):
        '''
        Takes a curie ID, detects the ontology from the curie id, and then queries UMLS to find the cui
        Params:
            curie_id - A string containing the curie id of the node. Formatted <source abbreviation>:<number> e.g. DOID:8398
            mesh_flag - True/False depending on if a mesh id is passed (defaults to false)

        current functionality
            "Mesh"
            "GO"
            "HP"
            "OMIM"

        '''
        if mesh_flag:
            df_cui = self.umls.get_cui_for_mesh_id(curie_id)
            if df_cui is not None:
                cui_list = list(df_cui['CUI'])
                return cui_list
        curie_list = curie_id.split(':')
        if curie_list[0] == "GO":
            df_cui = self.umls.get_cui_for_go_id(curie_id)
            if df_cui is not None:
                cui_list = list(df_cui['CUI'])
                return cui_list
        elif curie_list[0] == "HP":
            df_cui = self.umls.get_cui_for_hp_id(curie_id)
            if df_cui is not None:
                cui_list = list(df_cui['CUI'])
                return cui_list
        elif curie_list[0] == "OMIM":
            df_cui = self.umls.get_cui_for_omim_id(curie_id)
            if df_cui is not None:
                cui_list = list(df_cui['CUI'])
                return cui_list
        return None

    def get_cui_from_oxo(self, curie_id, mesh_flag = False):
        '''
        This formats the curie id then processes the reponse from query_oxo returning a list of cuis
        '''
        if type(curie_id) != str:
            curie_id = str(curie_id)
        if curie_id.startswith('REACT:'):
            curie_id = curie_id.replace('REACT', 'Reactome')
        if mesh_flag:
            mesh_id = 'MeSH:' + curie_id
            res = self.query_oxo(mesh_id)
        else:
            res = self.query_oxo(curie_id)
        cui=None
        if res is not None:
            res = res.json()
            cui = set()
            n_res = res['page']['totalElements']
            if int(n_res) > 0:
                mappings = res['_embedded']['mappings']
                for mapping in mappings:
                    if mapping['fromTerm']['curie'].startswith('UMLS'):
                        cui|= set([mapping['fromTerm']['curie'].split(':')[1]])
                    elif mapping['toTerm']['curie'].startswith('UMLS'):
                        cui|= set([mapping['toTerm']['curie'].split(':')[1]])
            if len(cui) == 0:
                cui = None
            else:
                cui = list(cui)
        return cui

    def get_cui_for_name(self, name, umls_flag = False):
        '''
        takes a string and then converts it to a cui or list of cuis by first querying SemRep then UMLS
        '''
        if not umls_flag:
            res = self.QuerySemRep(name)
            if res is not None:
                entities = res['entity']
            else:
                entities = []
        else:
            entities = []
        if len(entities) > 0:
            cuis = [None]*len(entities)
            c = 0
            for entity in entities:
                cuis[c] = entity['cui']
                c+=1
        else: 
            cuis = None
        if cuis is None:
            name = name.replace("'", "")
            name_list = name.lower().split(' ')
            if len(name_list) > 1:
                cuis = self.umls.get_cui_cloud_for_multiple_words(name_list)
            else:
                cuis = self.umls.get_cui_cloud_for_word(name.lower())
            if cuis is not None:
                cuis = cuis['CUI'].tolist()
        if cuis is not None:
            if len(cuis) > 10:
                cuis = list(numpy.random.choice(cuis,10,replace=False))
        return cuis

    def get_cui_for_id(self, curie_id, mesh_flag=False):
        '''
        Converts curie ids (or mesh ids) into cuis by querying the fiollowing services in the order listed:
        *MyChem
        *MyGene
        *EMBL-EBI OXO
        *UMLS
        '''
        cuis = None
        if not mesh_flag:
            if curie_id.upper().startswith('CHEMBL'):
                if curie_id.startswith('CHEMBL.COMPOUND'):
                    curie_id = curie_id.split(':')[1]
                cuis = QueryMyChem.get_cui(curie_id)
                if cuis is not None:
                    cuis = [cuis]
            elif curie_id.startswith('UniProt'):
                cuis = []
                try:
                    res = self.mg.get_cui(curie_id)
                    if res is not None:
                        cuis += res
                except requests.exceptions.HTTPError:
                    print('myGene Servers are busy')
                try:
                    res = self.mg.convert_uniprot_id_to_entrez_gene_ID(curie_id.split(':')[1])
                    if res is not None:
                        cuis += [str(eid) for eid in res]
                except requests.exceptions.HTTPError:
                    print('myGene Servers are busy')
                if len(cuis) == 0:
                    cuis = None
            elif curie_id.startswith('NCBIGene'):
                cuis = [curie_id.split(':')[1]]
                try:
                    res = self.mg.get_cui(curie_id)
                    if res is not None:
                        cuis += res
                except requests.exceptions.HTTPError:
                    print('myGene Servers are busy')
        if cuis is None:
            cuis = self.get_cui_from_oxo(curie_id, mesh_flag)
        if cuis is None:
            cuis = self.get_cui_from_umls(curie_id, mesh_flag)
        return cuis

    def get_edges_for_node(self, curie_id, name, predicate = None, mesh_flag=False):
        '''
        Takes the curie id and name for a node and finds all the edges connected to it
        Params
            * curie_id - A string containing the curie id of the node
            * name - A string containing the name of the node
            * predicate - A string containing the predivate you wish to return (defaults to None which means all predicates)
            * mesh_flag - A boolien indicating if the input is a mesh id (defaults to False)
        '''
        cuis = self.get_cui_for_id(curie_id, mesh_flag)
        df = None
        if cuis is not None:
            dfs = [None]*2*len(cuis)
            c=0
            for cui in cuis:
                dfs[c] = self.smdb.get_edges_for_subject_cui(cui, predicate = predicate)
                if dfs[c] is not None:
                    dfs.insert(0,'SUBJECT_INPUT', [name]*len(df))
                    df['OBJECT_INPUT'] = ['nan']*len(df)
                c+=1
                dfs[c] = self.smdb.get_edges_for_object_cui(cui, predicate = predicate)
                if dfs[c] is not None:
                    dfs.insert(0,'SUBJECT_INPUT', ['nan']*len(df))
                    df['OBJECT_INPUT'] = [name]*len(df)
                c+=1
            try:
                df = pandas.concat([x for x in dfs if x is not None],ignore_index=True)
            except ValueError:
                df = None
        if df is None:
            cuis = self.get_cui_for_name(name)
            if cuis is not None:
                if cuis is not None:
                    dfs = [None]*len(cuis)
                    c=0
                    for cui in cuis:
                        dfs[c] = self.smdb.get_edges_for_subject_cui(cui, predicate = predicate)
                        if dfs[c] is not None:
                            dfs[c].insert(0,'SUBJECT_INPUT', [name]*len(dfs[c]))
                            dfs[c]['OBJECT_INPUT'] = ['nan']*len(dfs[c])
                        c+=1
                        dfs[c] = self.smdb.get_edges_for_object_cui(cui, predicate = predicate)
                        if dfs[c] is not None:
                            dfs[c].insert(0,'SUBJECT_INPUT', ['nan']*len(dfs[c]))
                            dfs[c]['OBJECT_INPUT'] = [name]*len(dfc[c])
                    try:
                        df = pandas.concat([x for x in dfs if x is not None],ignore_index=True)
                    except ValueError:
                        df = None
        return df

    def get_edges_between_subject_object_with_pivot(self, subj_id, subj_name, obj_id, obj_name, pivot = 0, mesh_flags = [False, False]):
        '''
        takes the curie id and name of 2 nodes and finds the edges between them with a specified number of hops
        Params
            * subj_id - The curie id for the subject
            * subj_name - The name of the subject
            * obj_id - The curie id for the object
            * obj_name - The name of the object
            * pivot - an integer dictating the the number of pivot nodes to use between the subject and object (defaults to 0 i.e. directly connected)
            * mesh_flags - A 2 element list of boolian values dictating if each input is a mesh id (default set to [False, False])
        '''
        assert len(mesh_flags) == 2
        subj_cuis = self.get_cui_for_id(subj_id, mesh_flags[0])
        obj_cuis = self.get_cui_for_id(obj_id, mesh_flags[1])
        df = None
        if (subj_cuis and obj_cuis) is not None:
            dfs = []
            for subj_cui in subj_cuis:
                for obj_cui in obj_cuis:
                    edges = self.smdb.get_edges_between_subject_object_with_pivot(subj_cui, obj_cui, pivot = pivot)
                    if edges is not None:
                        dfs.append(edges)
            try:
                df = pandas.concat(dfs,ignore_index=True).drop_duplicates()
            except ValueError:
                df = None
        if df is None:
            new_subj_cuis = self.get_cui_for_name(subj_name)
            new_obj_cuis = self.get_cui_for_name(obj_name)
            if new_obj_cuis == obj_cuis and new_subj_cuis == subj_cuis:
                subj_cuis = None
                obj_cuis = None
            else:
                if new_subj_cuis is not None:
                    subj_cuis = new_subj_cuis
                if new_obj_cuis is not None:
                    obj_cuis = new_obj_cuis
            if (subj_cuis and obj_cuis) is not None:
                dfs = []
                for subj_cui in subj_cuis:
                    for obj_cui in obj_cuis:
                        edges = self.smdb.get_edges_between_subject_object_with_pivot(subj_cui, obj_cui, pivot = pivot)
                        if edges is not None:
                            dfs.append(edges)
                try:
                    df = pandas.concat(dfs,ignore_index=True).drop_duplicates()
                except ValueError:
                    df = None
        return df

    def get_shortest_path_between_subject_object(self, subj_id, subj_name, obj_id, obj_name, max_length = 3, mesh_flags = [False, False]):
        '''
        Takes a subject and a object then finds the sortest path between them up to some maximum height
        Params
            * subj_id - The curie id for the subject
            * subj_name - The name of the subject
            * obj_id - The curie id for the object
            * obj_name - The name of the object
            * max_length - an integer dictating the maximum length this function should check for the shorest path (defaults to 3)
            * mesh_flags - A 2 element list of boolian values dictating if each input is a mesh id (default set to [False, False])
        '''
        assert max_length > 0
        assert len(mesh_flags) == 2
        subj_cuis = self.get_cui_for_id(subj_id, mesh_flags[0])
        obj_cuis = self.get_cui_for_id(obj_id, mesh_flags[1])
        name_subj_cuis = self.get_cui_for_name(subj_name)
        name_obj_cuis = self.get_cui_for_name(obj_name)
        if name_subj_cuis == subj_cuis and name_obj_cuis == obj_cuis:
            name_subj_cuis = None
            name_obj_cuis = None
        df = None
        for n in range(max_length):
            if subj_cuis is not None and obj_cuis is not None:
                dfs = []
                for subj_cui in subj_cuis:
                    for obj_cui in obj_cuis:
                        edges = self.smdb.get_edges_between_subject_object_with_pivot(subj_cui, obj_cui, pivot = n)
                        if edges is not None:
                            dfs.append(edges)
                if len(dfs) > 0:
                    df = pandas.concat(dfs,ignore_index=True).drop_duplicates()
                if df is not None:
                    return df
            if name_subj_cuis is not None and name_obj_cuis is not None:
                dfs = []
                for subj_cui in name_subj_cuis:
                    for obj_cui in name_obj_cuis:
                        edges = self.smdb.get_edges_between_subject_object_with_pivot(subj_cui, obj_cui, pivot = n)
                        if edges is not None:
                            dfs.append(edges)
                if len(dfs) > 0:
                    df = pandas.concat(dfs,ignore_index=True).drop_duplicates()
                if df is not None:
                    return df
        return None

    def get_edges_between_nodes(self, subj_id, subj_name, obj_id, obj_name, predicate = None, result_col = ['PMID', 'SUBJECT_NAME', 'PREDICATE', 'OBJECT_NAME'], bidirectional=True, mesh_flags = [False, False]):
        '''
        This takes two nodes and finds the edges between them.
        current result_column options:
            * 'PMID' 
            * 'PREDICATE'
            * 'SUBJECT__CUI'
            * 'SUBJECT_NAME'
            * 'SUBJECT_SEMTYPE'
            * 'OBJECT__CUI'
            * 'OBJECT_NAME'
            * 'OBJECT_SEMTYPE'
        Params
            * subj_id - The curie id for the subject
            * subj_name - The name of the subject
            * obj_id - The curie id for the object
            * obj_name - The name of the object
            * predicate - A string containing the predicate you wish to search for (defaults to None which means return all predicates)\
            * result_col - A list of strings containing the columns you wish to return (defaults to ['PMID', 'SUBJECT_NAME', 'PREDICATE', 'OBJECT_NAME'])
            * bidirectional - boolian value dictating weither results should be bidirectional (defaults to True)
            * mesh_flags - A 2 element list of boolian values dictating if each input is a mesh id (default set to [False, False])
        '''
        subj_cuis = self.get_cui_for_id(subj_id, mesh_flags[0])
        obj_cuis = self.get_cui_for_id(obj_id, mesh_flags[1])
        df = None
        if subj_cuis is not None and obj_cuis is not None:
            dfs = []
            for subj_cui in subj_cuis:
                for obj_cui in obj_cuis:
                    if bidirectional:
                        edges = self.smdb.get_edges_between_subject_object(subj_cui, obj_cui, predicate = predicate, result_col = result_col)
                        edges2 = self.smdb.get_edges_between_subject_object(obj_cui, subj_cui, predicate = predicate, result_col = result_col)
                        if edges is not None:
                            edges.insert(0,'SUBJECT_INPUT', [subj_name]*len(edges))
                            edges['OBJECT_INPUT'] = [obj_name]*len(edges)
                            dfs.append(edges)
                        if edges2 is not None:
                            edges2.insert(0,'SUBJECT_INPUT', [obj_name]*len(edges2))
                            edges2['OBJECT_INPUT'] = [subj_name]*len(edges2)
                            dfs.append(edges2)
                    else:
                        edges = self.smdb.get_edges_between_subject_object(subj_cui, obj_cui, predicate = predicate, result_col = result_col)
                        if edges is not None:
                            edges.insert(0,'SUBJECT_INPUT', [subj_name]*len(edges))
                            edges['OBJECT_INPUT'] = [obj_name]*len(edges)
                            dfs.append(edges)
            try:
                df = pandas.concat(dfs,ignore_index=True).drop_duplicates()
            except ValueError:
                df = None
        if df is None:
            new_subj_cuis = self.get_cui_for_name(subj_name)
            new_obj_cuis = self.get_cui_for_name(obj_name)
            if new_obj_cuis == obj_cuis and new_subj_cuis == subj_cuis:
                subj_cuis = None
                obj_cuis = None
            else:
                if new_subj_cuis is not None:
                    subj_cuis = new_subj_cuis
                if new_obj_cuis is not None:
                    obj_cuis = new_obj_cuis
            if (subj_cuis and obj_cuis) is not None:
                dfs = []
                for subj_cui in subj_cuis:
                    for obj_cui in obj_cuis:
                        if bidirectional:
                            edges = self.smdb.get_edges_between_nodes(subj_cui, obj_cui, predicate = predicate, result_col = result_col)
                            if edges is not None:
                                dfs.append(edges)
                        else:
                            edges = self.smdb.get_edges_between_subject_object(subj_cui, obj_cui, predicate = predicate, result_col = result_col)
                            if edges is not None:
                                dfs.append(edges)
                try:
                    df = pandas.concat(dfs,ignore_index=True).drop_duplicates()
                except ValueError:
                    df = None
        return df

    def get_node_info(self, constraints, output, bidirectional = False):
        '''
        This finds a node in SemMedDB using a dict of constraints and then return requested output.
        Params:
            * contraints = a dict containing the contraints you wish to find the node with. All values should be strings e.g. {'field': 'value'}
            * output a list of fields you wish to retrieve\
        Avalable feilds for constaints and outputs :
            * 'PMID'
            * 'SUBJECT_CUI'
            * 'SUBJECT_NAME'
            * 'SUBJECT_SEMTYPE'
            * 'OBJECT_CUI'
            * 'OBJECT_NAME'
            * 'OBJECT_SEMTYPE'
            * 'PREDICATE'
        '''
        keys = [
            'PMID', 
            'SUBJECT_CUI', 
            'SUBJECT_NAME', 
            'SUBJECT_SEMTYPE',
            'OBJECT_CUI',
            'OBJECT_NAME',
            'OBJECT_SEMTYPE',
            'PREDICATE']

        output = [x.upper() for x in output]
        constraints = {x.upper(): v for x, v in constraints.items()}
        inputKeys = list(constraints.keys())

        assert type(constraints) == dict and type(output) == list
        if not set(inputKeys) < set(keys):
            print('Invalid field inputs in constraints argument: ' + ', '.join(list(set(inputKeys) - set(keys))))
            print('Valid fields are the following:')
            print(', '.join(keys))
            return None
        if not set(output) < set(keys):
            print('Invalid field inputs in output argument: ' + ', '.join(list(set(output) - set(keys))))
            print('Valid fields are the following:')
            print(', '.join(keys))
            return None
        query = 'select distinct ' + ', '.join(output) + ' from SPLIT_PREDICATION where '
        for key in inputKeys:
            query += key + " = '" + constraints[key].replace("'", '') + "' and "
        query = query[:-5]
        df = self.smdb.get_dataframe_from_db(query)
        if df is not None and bidirectional:
            df['orientation'] = ['original']*len(df)
        df2 = None
        if bidirectional:
            query_list = query.split(' ')
            for a in range(len(query_list)):
                if 'OBJECT' in query_list[a]:
                    query_list[a] = query_list[a].replace('OBJECT', 'SUBJECT')
                elif 'SUBJECT' in query_list[a]:
                    query_list[a] = query_list[a].replace('SUBJECT', 'OBJECT')
            query2 = ' '.join(query_list)
            df2 = self.smdb.get_dataframe_from_db(query2)
            if df2 is not None:
                df['orientation'] = ['inverted']*len(df)
        if df2 is None:
            return df
        elif df is None:
            return df2
        else:
            return pandas.concat([df,df2], ignore_index = True)

    def get_node_from_cui(self, cui, name_flag = False):
        '''
        This takes a cui then looks up corresponding curie ids or names from a provided csv generated using BuildCuiCache.py
        Params:
            * cui - A string containing the cui you wish to convert
            * name_flag - A boolean indicating what to return. (curie id if False, name if True) This defaults to False
        '''
        if cui in self.cui_dict.keys():
            curie_ids = self.cui_dict[cui]
            if name_flag:
                names = []
                for curie_id in curie_ids:
                    names += [self.map_df.loc[self.map_df['id'] == curie_id, 'name'].iloc[0]]
                return names
            return curie_ids
        else:
            return None


if __name__ == '__main__':
    pass


