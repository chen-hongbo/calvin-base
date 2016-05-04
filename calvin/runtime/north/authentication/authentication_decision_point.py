# -*- coding: utf-8 -*-

# Copyright (c) 2016 Ericsson AB
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import re
import os
from calvin.utilities.calvin_callback import CalvinCB
from calvin.utilities.calvinlogger import get_logger
from passlib.hash import pbkdf2_sha256

_log = get_logger(__name__)

class AuthenticationDecisionPoint(object):

    def __init__(self, node, config=None):
        _log.info("__init__")
        # Default config
        self.config = {
            "policy_storage": "files",
            "policy_name_pattern": "*"
        }
        if config is not None:
            # Change some of the default values of the config.
            self.config.update(config)
        self.node = node
        self.registered_nodes = {}


    def authenticate(self, request, callback):
        """
        Use policies to return access decision for the request.

        The request and response format is inspired by the XACML JSON Profile 
        but has been simplified to be more compact.

        Request (example):
        {
            "subject": {
                "user": ["user1"],
                "password": ["signer"]
            },
            "resource": {
                "node_id": "a77c0687-dce8-496f-8d81-571333be6116"
            }
        }

        Response (example):
        {
            "decision": "permit",
            "subject_attributes":
                {
                    "first_name":["Anders"],
                    "last_name":["Andersson"],
                    "organization":["Ericsson","3GPP"],
                    "age":["11"]
                },
            "obligations": [
                {
                    "id": "time_range",
                    "attributes": {
                        "start_time": "09:00",
                        "end_time": "17:00"
                    }
                }
            ]
        }
        """
        _log.debug("authenticate::request received: %s" % request)
        if "resource" in request and "node_id" in request["resource"]:
            try:
                node_id = request["resource"]["node_id"]
                request["resource"] = self.registered_nodes[node_id]
                request["resource"]["node_id"] = node_id
            except Exception:
                pass

        decisions = []
        obligations = []
        #authentication_decision, policy_obligations = self.authentication_decision(request)
        subject_attributes = self.authentication_decision(request)
        #TODO: add support for obligations, if it makes any sense??? 
#        if policy_obligations:
#            obligations.append(policy_obligations)
        callback(auth_response=self.create_response(subject_attributes, obligations))

        return (subject_attributes, obligations)



    def create_response(self, subject_attributes, obligations):
        """Return authorization response including decision and obligations."""
        response = {}
        response["subject_attributes"] = subject_attributes
        if obligations:
            response["obligations"] = obligations
        return response


    def authentication_decision(self, request):
        _log.debug("authentication_decision::request%s" % request)
        users_db = self.node.authentication.arp.get_users_db()
        groups_db = self.node.authentication.arp.get_groups_db()
        # Verify users against stored passwords
        subject_attributes = {}
        for user in users_db['users_db']:
            if request['subject']['user'] == user['username']:
                if pbkdf2_sha256.verify(request['subject']['password'],user['password']):
                    for key in user['attributes']:
                        if key == "groups" and groups_db:
                            for groupKey in user['attributes']['groups']:
                                for groupAttribute in groups_db[groupKey]:
                                    if not groupAttribute in subject_attributes:
                                        #if the is no key, create array and add firs value
                                        subject_attributes.setdefault(groupAttribute, []).append(groups_db[groupKey][groupAttribute])
                                    elif not groups_db[groupKey][groupAttribute] in subject_attributes[groupAttribute]:
                                        #list exist, make sure we don't add same value several times
                                        subject_attributes[groupAttribute].append(groups_db[groupKey][groupAttribute])
                        else:
                            if not user['attributes'][key] in subject_attributes:
                                #if the is no key, create array and add firsit value
                                subject_attributes.setdefault(key, []).append(user['attributes'][key])
                            elif not user['attributes'][key] in subject_attributes[key]:
                                #list exist, make sure we don't add same value several times
                                subject_attributes[key].append(user['attributes'][key])
                    return subject_attributes
        return None
 

