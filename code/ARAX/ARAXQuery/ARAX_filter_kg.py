#!/bin/env python3
import sys
def eprint(*args, **kwargs): print(*args, file=sys.stderr, **kwargs)

import os
import json
import ast
import re
import numpy as np
from response import Response
import traceback


class ARAXFilterKG:

    #### Constructor
    def __init__(self):
        self.response = None
        self.message = None
        self.parameters = None
        self.allowable_actions = {
            'remove_edges_by_type',
            'remove_edges_by_attribute',
            'remove_nodes_by_type'
        }

    def describe_me(self):
        """
        Little helper function for internal use that describes the actions and what they can do
        :return:
        """
        for action in self.allowable_actions:
            getattr(self, '_' + self.__class__.__name__ + '__' + action)(describe=True)

    # Write a little helper function to test parameters
    def check_params(self, allowable_parameters):
        """
        Checks to see if the input parameters are allowed
        :param input_parameters: input parameters supplied to ARAXOverlay.apply()
        :param allowable_parameters: the allowable parameters
        :return: None
        """
        for key, item in self.parameters.items():
            if key not in allowable_parameters:
                self.response.error(
                    f"Supplied parameter {key} is not permitted. Allowable parameters are: {list(allowable_parameters.keys())}",
                    error_code="UnknownParameter")
            elif item not in allowable_parameters[key]:
                if any([type(x) == float for x in allowable_parameters[key]]):  # if it's a float, just accept it as it is
                    return
                else:  # otherwise, it's really not an allowable parameter
                    self.response.error(
                        f"Supplied value {item} is not permitted. In action {allowable_parameters['action']}, allowable values to {key} are: {list(allowable_parameters[key])}",
                        error_code="UnknownValue")



    #### Top level decision maker for applying filters
    def apply(self, input_message, input_parameters):

        #### Define a default response
        response = Response()
        self.response = response
        self.message = input_message

        #### Basic checks on arguments
        if not isinstance(input_parameters, dict):
            response.error("Provided parameters is not a dict", error_code="ParametersNotDict")
            return response

        # list of actions that have so far been created for ARAX_overlay
        allowable_actions = self.allowable_actions

        # check to see if an action is actually provided
        if 'action' not in input_parameters:
            response.error(f"Must supply an action. Allowable actions are: action={allowable_actions}", error_code="MissingAction")
        elif input_parameters['action'] not in allowable_actions:
            response.error(f"Supplied action {input_parameters['action']} is not permitted. Allowable actions are: {allowable_actions}", error_code="UnknownAction")

        #### Return if any of the parameters generated an error (showing not just the first one)
        if response.status != 'OK':
            return response

        # populate the parameters dict
        parameters = dict()
        for key, value in input_parameters.items():
            parameters[key] = value

        #### Store these final parameters for convenience
        response.data['parameters'] = parameters
        self.parameters = parameters

        # convert the action string to a function call (so I don't need a ton of if statements
        getattr(self, '_' + self.__class__.__name__ + '__' + parameters['action'])()  # thank you https://stackoverflow.com/questions/11649848/call-methods-by-string

        response.debug(f"Applying Overlay to Message with parameters {parameters}")  # TODO: re-write this to be more specific about the actual action

        #### Return the response and done
        return response

    def __remove_edges_by_type(self, describe=False):
        """
        Removes edges from the KG.
        Allowable parameters: {'edge_type': str, 
                                'edge_property': str,
                                'direction': {'above', 'below'}}
        :return:
        """
        message = self.message
        parameters = self.parameters
        # make a list of the allowable parameters (keys), and their possible values (values). Note that the action and corresponding name will always be in the allowable parameters
        if message and parameters and hasattr(message, 'query_graph') and hasattr(message.query_graph, 'edges'):
            allowable_parameters = {'action': {'remove_edges_by_type'},
                                    'edge_type': set([x.type for x in self.message.knowledge_graph.edges]),
                                    'remove_connected_nodes': {'true', 'false', 'True', 'False', 't', 'f'}
                                }
        else:
            allowable_parameters = {'action': {'remove_edges_by_type'},
                                    'edge_type': {'an edge type'},
                                    'remove_connected_nodes': {'true', 'false', 'True', 'False', 't', 'f'}
                                }

        # A little function to describe what this thing does
        if describe:
            print(allowable_parameters)
            return

        # Make sure only allowable parameters and values have been passed
        self.check_params(allowable_parameters)
        # return if bad parameters have been passed
        if self.response.status != 'OK':
            return self.response

        edge_params = self.parameters
        if 'remove_connected_nodes' in edge_params:
            value = edge_params['remove_connected_nodes']
            if value in {'true', 'True', 't'}:
                edge_params['remove_connected_nodes'] = True
            elif value in {'false', 'False', 'F'}:
                edge_params['remove_connected_nodes'] = False
            else:
                self.response.error(f"Supplied value {value} is not permitted. In parameter remove_connected_nodes, allowable values are: {list(allowable_parameters['remove_connected_nodes'])}",
                    error_code="UnknownValue")
        else:
            edge_params['remove_connected_nodes'] = False

        # now do the call out to NGD
        from Filter_KG.remove_edges import RemoveEdges
        RE = RemoveEdges(self.response, self.message, edge_params)
        response = RE.remove_edges_by_type()
        return response

    def __remove_edges_by_attribute(self, describe=False):
        """
        Removes edges from the KG.
        Allowable parameters: {'edge_type': str, 
                                'edge_attribute': str,
                                'direction': {'above', 'below'}}
        :return:
        """
        message = self.message
        parameters = self.parameters
        # make a list of the allowable parameters (keys), and their possible values (values). Note that the action and corresponding name will always be in the allowable parameters
        if message and parameters and hasattr(message, 'knowledge_graph') and hasattr(message.knowledge_graph, 'edges'):
            known_attributes = set()
            for edge in message.knowledge_graph.edges:
                if hasattr(edge, 'edge_attributes'):
                    for attribute in edge.edge_attributes:
                        known_attributes.add(attribute.name)
            print(known_attributes)
            allowable_parameters = {'action': {'remove_edges_by_attribute'},
                                    'edge_attribute': known_attributes,
                                    'direction': {'above', 'below'},
                                    'threshold': {float()},
                                    'remove_connected_nodes': {'true', 'false', 'True', 'False', 't', 'f'}
                                    }
        else:
            allowable_parameters = {'action': {'remove_edges_by_attribute'},
                                    'edge_attribute': {'an edge attribute name'},
                                    'direction': {'above', 'below'},
                                    'threshold': {'a floating point number'},
                                    'remove_connected_nodes': {'true', 'false', 'True', 'False', 't', 'f'}
                                    }

        # A little function to describe what this thing does
        if describe:
            print(allowable_parameters)
            return

        edge_params = self.parameters

        # try to convert the threshold to a float
        try:
            edge_params['threshold'] = float(edge_params['threshold'])
        except:
            tb = traceback.format_exc()
            error_type, error, _ = sys.exc_info()
            self.response.error(tb, error_code=error_type.__name__)
            self.response.error(f"parameter 'threshold' must be a float")
        if self.response.status != 'OK':
            return self.response

        # Make sure only allowable parameters and values have been passed
        self.check_params(allowable_parameters)
        # return if bad parameters have been passed
        if self.response.status != 'OK':
            return self.response

        if 'remove_connected_nodes' in edge_params:
            value = edge_params['remove_connected_nodes']
            if value in {'true', 'True', 't'}:
                edge_params['remove_connected_nodes'] = True
            elif value in {'false', 'False', 'F'}:
                edge_params['remove_connected_nodes'] = False
            else:
                self.response.error(
                    f"Supplied value {value} is not permitted. In parameter remove_connected_nodes, allowable values are: {list(allowable_parameters['remove_connected_nodes'])}",
                    error_code="UnknownValue")
        else:
            edge_params['remove_connected_nodes'] = False

        if 'direction' not in edge_params:
            self.response.error(
                f"Direction must be provided, allowable directions are: {list(allowable_parameters['direction'])}",
                error_code="UnknownValue")
        if self.response.status != 'OK':
            return self.response

        # now do the call out to NGD
        from Filter_KG.remove_edges import RemoveEdges
        RE = RemoveEdges(self.response, self.message, edge_params)
        response = RE.remove_edges_by_attribute()
        return response

    def __remove_nodes_by_type(self, describe=False):
        """
        Removes nodes from the KG.
        Allowable parameters: {'node_type': str, 
                                'node_property': str,
                                'direction': {'above', 'below'}}
        :return:
        """
        message = self.message
        parameters = self.parameters
        # make a list of the allowable parameters (keys), and their possible values (values). Note that the action and corresponding name will always be in the allowable parameters
        if message and parameters and hasattr(message, 'query_graph') and hasattr(message.query_graph, 'nodes'):
            allowable_parameters = {'action': {'remove_nodes_by_type'},
                                    'node_type': set([t for x in self.message.knowledge_graph.nodes for t in x.type])
                                   }
        else:
            allowable_parameters = {'action': {'remove_nodes_by_type'}, 
                                'node_type': {'a node type'}}

        # A little function to describe what this thing does
        if describe:
            print(allowable_parameters)
            return

        # Make sure only allowable parameters and values have been passed
        self.check_params(allowable_parameters)
        # return if bad parameters have been passed
        if self.response.status != 'OK':
            return self.response

        node_params = self.parameters

        # now do the call out to NGD
        from Filter_KG.remove_nodes import RemoveNodes
        RN = RemoveNodes(self.response, self.message, node_params)
        response = RN.remove_nodes_by_type()
        return response

##########################################################################################
def main():
    ### Note that most of this is just manually doing what ARAXQuery() would normally do for you

    #### Create a response object
    response = Response()

    #### Create an ActionsParser object
    from actions_parser import ActionsParser
    actions_parser = ActionsParser()

    #### Set a simple list of actions
    # actions_list = [
    #    "overlay(compute_confidence_scores=true)",
    #    "return(message=true,store=false)"
    # ]

    actions_list = [
        #"filter_kg(action=remove_edges_by_type, edge_type=physically_interacts_with, remove_connected_nodes=false)",
        #"filter_kg(action=remove_edges_by_type, edge_type=physically_interacts_with, remove_connected_nodes=something)",
        #"filter(action=remove_nodes_by_type, node_type=protein)",
        "overlay(action=compute_ngd)",
        "filter(action=remove_edges_by_attribute, edge_attribute=ngd, threshold=.08, direction=below, remove_connected_nodes=False)",
        "return(message=true,store=false)"
    ]

    #### Parse the action_list and print the result
    result = actions_parser.parse(actions_list)
    response.merge(result)
    if result.status != 'OK':
        print(response.show(level=Response.DEBUG))
        return response
    actions = result.data['actions']

    #### Read message #2 from the database. This should be the acetaminophen proteins query result message
    sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/../../UI/Feedback")
    from RTXFeedback import RTXFeedback
    araxdb = RTXFeedback()

    message_dict = araxdb.getMessage(2)  # acetaminophen2proteins graph
    # message_dict = araxdb.getMessage(13)  # ibuprofen -> proteins -> disease # work computer
    # message_dict = araxdb.getMessage(14)  # pleuropneumonia -> phenotypic_feature # work computer
    # message_dict = araxdb.getMessage(16)  # atherosclerosis -> phenotypic_feature  # work computer
    # message_dict = araxdb.getMessage(5)  # atherosclerosis -> phenotypic_feature  # home computer
    # message_dict = araxdb.getMessage(10)

    #### The stored message comes back as a dict. Transform it to objects
    from ARAX_messenger import ARAXMessenger
    message = ARAXMessenger().from_dict(message_dict)
    # print(json.dumps(ast.literal_eval(repr(message)),sort_keys=True,indent=2))

    #### Create an overlay object and use it to apply action[0] from the list
    #filterkg = ARAXFilterKG()
    #result = filterkg.apply(message, actions[0]['parameters'])
    #response.merge(result)

    # Apply overlay so you get an edge attribute to work with, then apply the filter
    from ARAX_overlay import ARAXOverlay
    overlay = ARAXOverlay()
    result = overlay.apply(message, actions[0]['parameters'])
    response.merge(result)
    # then apply the filter
    filterkg = ARAXFilterKG()
    result = filterkg.apply(message, actions[1]['parameters'])
    response.merge(result)

    # if result.status != 'OK':
    #    print(response.show(level=Response.DEBUG))
    #    return response
    # response.data = result.data

    #### If successful, show the result
    # print(response.show(level=Response.DEBUG))
    # response.data['message_stats'] = { 'n_results': message.n_results, 'id': message.id,
    #    'reasoner_id': message.reasoner_id, 'tool_version': message.tool_version }
    # response.data['message_stats']['confidence_scores'] = []
    # for result in message.results:
    #    response.data['message_stats']['confidence_scores'].append(result.confidence)

    # print(json.dumps(ast.literal_eval(repr(response.data['parameters'])),sort_keys=True,indent=2))
    # print(json.dumps(ast.literal_eval(repr(response.data['message_stats'])),sort_keys=True,indent=2))
    # a comment on the end so you can better see the network on github

    # look at the response
    # print(response.show(level=Response.DEBUG))
    # print(response.show())
    # print("Still executed")

    # look at the edges
    # print(json.dumps(ast.literal_eval(repr(message.knowledge_graph.edges)),sort_keys=True,indent=2))
    # print(json.dumps(ast.literal_eval(repr(message.knowledge_graph.nodes)), sort_keys=True, indent=2))
    # print(json.dumps(ast.literal_eval(repr(message)), sort_keys=True, indent=2))
    # print(response.show(level=Response.DEBUG))

    # just print off the values
    # print(json.dumps(ast.literal_eval(repr(message.knowledge_graph.edges)), sort_keys=True, indent=2))
    # for edge in message.knowledge_graph.edges:
    #    if hasattr(edge, 'edge_attributes') and edge.edge_attributes and len(edge.edge_attributes) >= 1:
    #        print(edge.edge_attributes.pop().value)
    print(json.dumps(ast.literal_eval(repr(message.knowledge_graph.edges)), sort_keys=True, indent=2))
    print(response.show(level=Response.DEBUG))
    # print(actions_parser.parse(actions_list))

if __name__ == "__main__": main()
