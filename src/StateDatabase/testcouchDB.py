# Copyright (c) 2019 Universidade da Coruña
# Authors:
#     - Jonatan Enes [main](jonatan.enes@udc.es, jonatan.enes.alvarez@gmail.com)
#     - Roberto R. Expósito
#     - Juan Touriño
#
# This file is part of the ServerlessContainers framework, from
# now on referred to as ServerlessContainers.
#
# ServerlessContainers is free software: you can redistribute it
# and/or modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation, either version 3
# of the License, or (at your option) any later version.
#
# ServerlessContainers is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with ServerlessContainers. If not, see <http://www.gnu.org/licenses/>.


from unittest import TestCase

from src.StateDatabase.couchdb import CouchDBServer
from src.Guardian.Guardian import Guardian
from test.documents.limits import base_limits
from test.documents.rules import cpu_exceeded_upper, CpuRescaleUp
from test.documents.structures import base_container


class DocumentTest(TestCase):
    __database = None
    __database_type = None
    __server_address = "localhost"
    __server_port = "5984"

    def set_database(self, database_type, database_test_name):
        self.__database_type = database_type
        self.__database = database_test_name

    def tearDown(self):
        self.handler.remove_database(self.__database)
        self.handler.close_connection()

    def setUp(self):
        self.handler = CouchDBServer(self.__server_address, self.__server_port)
        self.handler.set_database_name(self.__database_type, self.__database)
        if self.handler.database_exists(self.__database):
            self.handler.remove_database(self.__database)
        self.handler.create_database(self.__database)
        self.guardian = Guardian()


class StructureTest(DocumentTest):
    __database = "structures-test"
    __database_type = "structures"

    def setUp(self):
        super().set_database(self.__database_type, self.__database)
        super().setUp()

    def compare_structures(self, structure1, structure2):
        def compare_resources(resources1, resources2):
            for resource in ["cpu", "mem", "disk", "net", "energy"]:
                if resources1[resource] != resources2[resource]:
                    return False

        for key in ["type", "subtype", "guard_policy", "host", "host_rescaler_ip", "host_rescaler_port", "name",
                    "guard"]:
            if structure1[key] != structure2[key]:
                return False
        compare_resources(structure1["resources"], structure2["resources"])

        return True

    def testStructures(self):
        structure = dict(base_container)
        with self.assertRaises(ValueError):
            self.handler.get_structure(structure["name"])
        TestCase.assertEqual(self, first=0, second=len(self.handler.get_structures()))

        self.handler.add_structure(structure)
        retrieved_structure = self.handler.get_structure(structure["name"])
        TestCase.assertEqual(self, first=1, second=len(self.handler.get_structures()))
        TestCase.assertTrue(self, self.compare_structures(structure, retrieved_structure))

        modified_structure = retrieved_structure
        modified_structure["policy"] = "fixed"
        modified_structure["guard_policy"] = False
        modified_structure["resources"]["cpu"]["min"] += 100

        TestCase.assertTrue(self, self.handler.update_structure(modified_structure))
        retrieved_structure = self.handler.get_structure(structure["name"])
        TestCase.assertEqual(self, first=1, second=len(self.handler.get_structures()))
        TestCase.assertTrue(self, self.compare_structures(modified_structure, retrieved_structure))


class LimitsTest(DocumentTest):
    __database = "limits-test"
    __database_type = "limits"

    def compare_limits(self, structure1, structure2):
        for resource in ["cpu", "mem", "disk", "net", "energy"]:
            if structure1["resources"][resource] != structure2["resources"][resource]:
                return False

        for key in ["type", "name"]:
            if structure1[key] != structure2[key]:
                return False

        return True

    def setUp(self):
        super().set_database(self.__database_type, self.__database)
        super().setUp()

    def testLimits(self):
        limits = base_limits
        structure = dict(base_container)

        with self.assertRaises(ValueError):
            self.handler.get_limits(structure)
        TestCase.assertEqual(self, first=0, second=len(self.handler.get_all_limits()))

        self.handler.add_limit(limits)

        retrieved_limits = self.handler.get_limits(structure)
        TestCase.assertEqual(self, first=1, second=len(self.handler.get_all_limits()))
        TestCase.assertTrue(self, self.compare_limits(limits, retrieved_limits))

        modified_limits = retrieved_limits
        modified_limits["resources"]["cpu"]["upper"] += 100

        TestCase.assertTrue(self, self.handler.update_limit(modified_limits))
        retrieved_limits = self.handler.get_limits(structure)
        TestCase.assertEqual(self, first=1, second=len(self.handler.get_all_limits()))
        TestCase.assertTrue(self, self.compare_limits(modified_limits, retrieved_limits))


class EventsAndRequestsTest(DocumentTest):
    __server_address = "localhost"
    __server_port = "5984"

    def tearDown(self):
        self.handler.remove_database("events-test")
        self.handler.remove_database("requests-test")
        self.handler.close_connection()

    def setUp(self):
        self.handler = CouchDBServer(self.__server_address, self.__server_port)
        self.handler.set_database_name("events", "events-test")
        self.handler.set_database_name("requests", "requests-test")

        if self.handler.database_exists("events-test"):
            self.handler.remove_database("events-test")
        self.handler.create_database("events-test")

        if self.handler.database_exists("requests-test"):
            self.handler.remove_database("requests-test")
        self.handler.create_database("requests-test")

        self.guardian = Guardian()

    def testEvents(self):
        structure = {
            "guard": True,
            "guard_policy": "serverless",
            "host": "c14-13",
            "host_rescaler_ip": "c14-13",
            "host_rescaler_port": "8000",
            "name": "node0",
            "resources": {
                "cpu": {
                    "current": 140,
                    "guard": True,
                    "max": 200,
                    "min": 50
                },
                "energy": {
                    "guard": False,
                    "max": 20,
                    "min": 0,
                    "usage": 2.34
                },
                "mem": {
                    "current": 3072,
                    "guard": True,
                    "max": 10240,
                    "min": 512
                }
            },
            "subtype": "container",
            "type": "structure"
        }
        limits = {"resources": {"cpu": {"upper": 120, "lower": 80, "boundary": 20},
                                "mem": {"upper": 2048, "lower": 1024, "boundary": 1024},
                                "energy": {"upper": 20, "lower": 10, "boundary": 5}}
                  }
        usages = {"structure.cpu.usage": 100, "structure.mem.usage": 1536, "structure.energy.usage": 15}

        event_rules = [cpu_exceeded_upper]
        rescaling_rules = [CpuRescaleUp]
        for rule in event_rules + rescaling_rules:
            rule["active"] = True

        resource, rescale_rule, amount = "cpu", CpuRescaleUp, 100

        usages["structure." + resource + ".usage"] = limits["resources"][resource]["lower"] + amount
        events = list()

        num_needed_events = rescale_rule["rule"]["and"][0][">="][1]

        for i in range(num_needed_events):
            events += self.guardian.match_usages_and_limits(structure["name"], event_rules, usages, limits["resources"],
                                                            structure["resources"])
        reduced_events = self.guardian.reduce_structure_events(events)

        generated_requests, events_to_remove = self.guardian.match_rules_and_events(structure, rescaling_rules,
                                                                                    reduced_events,
                                                                                    limits["resources"],
                                                                                    usages)

        TestCase.assertEqual(self, first=0, second=len(self.handler.get_events(structure)))
        self.handler.add_events(events)
        TestCase.assertEqual(self, first=num_needed_events, second=len(self.handler.get_events(structure)))
        self.handler.delete_events(self.handler.get_events(structure))
        self.handler.compact_database("events-test")
        TestCase.assertEqual(self, first=0, second=len(self.handler.get_events(structure)))

        TestCase.assertEqual(self, first=0, second=len(self.handler.get_requests(structure)))
        self.handler.add_requests(generated_requests)
        TestCase.assertEqual(self, first=1, second=len(self.handler.get_requests(structure)))
        self.handler.delete_request(self.handler.get_requests(structure)[0])
        TestCase.assertEqual(self, first=0, second=len(self.handler.get_requests(structure)))
