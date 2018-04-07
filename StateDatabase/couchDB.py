# /usr/bin/python
import time

import requests
import json


class CouchDBServer:
    post_doc_headers = {'content-type': 'application/json'}

    __structures_db_name = "structures"
    __services_db_name = "services"
    __limits_db_name = "limits"
    __rules_db_name = "rules"
    __events_db_name = "events"
    __requests_db_name = "requests"
    __MAX_UPDATE_TRIES = 5

    def __init__(self, server='http://couchdb:5984'):
        self.server = server

    def database_exists(self, database):
        r = requests.head(self.server + "/" + database)
        return r.status_code == 200

    def create_database(self, database):
        r = requests.put(self.server + "/" + database)
        if r.status_code != 201:
            r.raise_for_status()
        else:
            return True

    def remove_database(self, database):
        r = requests.delete(self.server + "/" + database)
        if r.status_code != 200:
            r.raise_for_status()
        else:
            return True

    def get_all_database_docs(self, database):
        docs = list()
        r = requests.get(self.server + "/" + database + "/_all_docs")
        if r.status_code != 200:
            r.raise_for_status()
        else:
            rows = json.loads(r.text)["rows"]
            for row in rows:
                req_doc = requests.get(self.server + "/" + database + "/" + row["id"])
                docs.append(dict(req_doc.json()))
            return docs

    # PRIVATE CRUD METHODS #

    def __delete_doc(self, database, docid, rev):
        r = requests.delete(self.server + "/" + database + "/" + str(docid) + "?rev=" + str(rev))
        if r.status_code != 200:
            r.raise_for_status()
        else:
            return True

    def __add_doc(self, database, doc):
        r = requests.post(self.server + "/" + database, data=json.dumps(doc), headers=self.post_doc_headers)
        if r.status_code != 200:
            r.raise_for_status()
        else:
            return True

    def __resilient_update_doc(self, database, doc, previous_tries=0, time_backoff_seconds=2, new_fields=[]):
        r = requests.post(self.server + "/" + database, data=json.dumps(doc), headers=self.post_doc_headers)
        if r.status_code != 200:
            if r.status_code == 409:
                # Conflict error, document may have been updated (e.g., heartbeat of services),
                # update revision and retry
                if 0 <= previous_tries < self.__MAX_UPDATE_TRIES:
                    new_doc = self.find_documents_by_matches(database, {"_id": doc["_id"]})[0]
                    doc["_rev"] = new_doc["_rev"]
                    return self.__resilient_update_doc(database, doc, previous_tries + 1)
                else:
                    r.raise_for_status()
            elif r.status_code == 404:
                # Database may have been reinitialized (deleted and recreated), wait and retry again
                time.sleep(time_backoff_seconds)
                return self.__resilient_update_doc(database, doc, previous_tries + 1)
            else:
                r.raise_for_status()
        else:
            return True

    def find_documents_by_matches(self, database, selectors):
        query = {"selector": {}}

        for key in selectors:
            query["selector"][key] = selectors[key]

        req_docs = requests.post(self.server + "/" + database + "/_find", data=json.dumps(query),
                                 headers={'Content-Type': 'application/json'})
        if req_docs.status_code != 200:
            req_docs.raise_for_status()
        else:
            return req_docs.json()["docs"]

    # STRUCTURES #
    def add_structure(self, structure):
        return self.__add_doc(self.__structures_db_name, structure)

    def get_structure(self, structure_name):
        return dict(self.find_documents_by_matches(self.__structures_db_name, {"name": structure_name})[0])

    def get_structures(self, subtype=None):
        if subtype is None:
            return self.get_all_database_docs(self.__structures_db_name)
        else:
            return self.find_documents_by_matches(self.__structures_db_name, {"subtype": subtype})

    def update_structure(self, structure):
        return self.__resilient_update_doc(self.__structures_db_name, structure)

    # EVENTS #
    def add_events(self, events):
        for event in events:
            self.__add_doc(self.__events_db_name, event)

    def get_events(self, structure):
        return self.find_documents_by_matches(self.__events_db_name, {"structure": structure["name"]})

    def delete_num_events_by_structure(self, structure, event_name, event_num):
        num_deleted = 0
        events = self.get_all_database_docs(self.__events_db_name)
        for event in events:
            if event["structure"] == structure["name"] and event["name"] == event_name and num_deleted < event_num:
                self.__delete_doc(self.__events_db_name, event["_id"], event["_rev"])
                num_deleted += 1

    def delete_event(self, event):
        self.__delete_doc(self.__events_db_name, event["_id"], event["_rev"])

    def delete_events(self, events):
        for event in events:
            self.delete_event(event)

    # LIMITS #
    def add_limit(self, limit):
        return self.__add_doc(self.__limits_db_name, limit)

    def get_limits(self, structure):
        # Return just the first item, as it should only be one, otherwise return none
        limits = self.find_documents_by_matches(self.__limits_db_name, {"name": structure["name"]})
        if not limits:
            return None
        else:
            return limits[0]

    def update_limit(self, limit):
        return self.__resilient_update_doc(self.__limits_db_name, limit)

    # REQUESTS #
    def get_requests(self, structure=None):
        if structure is None:
            return self.get_all_database_docs(self.__requests_db_name)
        else:
            return self.find_documents_by_matches(self.__requests_db_name, {"structure": structure["name"]})

    def add_requests(self, reqs):
        for request in reqs:
            self.__add_doc(self.__requests_db_name, request)

    def delete_request(self, request):
        self.__delete_doc(self.__requests_db_name, request["_id"], request["_rev"])

    # RULES #
    def add_rule(self, rule):
        return self.__add_doc(self.__rules_db_name, rule)

    def get_rule(self, rule_name):
        docs = self.find_documents_by_matches(self.__rules_db_name, {"name": rule_name})
        if not docs:
            raise ValueError("Rule " + rule_name + " not found")
        else:
            # Return the first one as it should only be one
            return dict(docs[0])

    def get_rules(self):
        return self.get_all_database_docs(self.__rules_db_name)

    def update_rule(self, rule):
        return self.__resilient_update_doc(self.__rules_db_name, rule)

    # SERVICES #
    def get_service(self, service_name):
        docs = self.find_documents_by_matches(self.__services_db_name, {"name": service_name})
        if not docs:
            raise ValueError("Service " + service_name + " not found")
        else:
            # Return the first one as it should only be one
            return dict(docs[0])

    def add_service(self, service):
        return self.__add_doc(self.__services_db_name, service)

    def update_service(self, service):
        return self.__resilient_update_doc(self.__services_db_name, service)

    def delete_service(self, service):
        return self.__delete_doc(self.__services_db_name, service["_id"], service["_rev"])
