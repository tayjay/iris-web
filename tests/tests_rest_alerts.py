#  IRIS Source Code
#  Copyright (C) 2023 - DFIR-IRIS
#  contact@dfir-iris.org
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

from unittest import TestCase
from iris import Iris
from iris import IRIS_PERMISSION_ALERTS_READ
from iris import IRIS_PERMISSION_ALERTS_WRITE
from iris import IRIS_PERMISSION_ALERTS_DELETE

_IDENTIFIER_FOR_NONEXISTENT_OBJECT = 123456789


class TestsRestAlerts(TestCase):

    def setUp(self) -> None:
        self._subject = Iris()

    def tearDown(self):
        self._subject.clear_database()

    def test_create_alert_should_return_201(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create('/api/v2/alerts', body)
        self.assertEqual(201, response.status_code)

    def test_create_alert_should_return_data_alert_title(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create('/api/v2/alerts', body).json()
        self.assertEqual('title', response['alert_title'])

    def test_create_alert_should_return_data_alert_severity_id(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create('/api/v2/alerts', body).json()
        self.assertEqual(4, response['alert_severity_id'])

    def test_create_alert_should_return_data_alert_status_id(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create('/api/v2/alerts', body).json()
        self.assertEqual(3, response['alert_status_id'])

    def test_create_alert_should_return_data_alert_customer_id(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create('/api/v2/alerts', body).json()
        self.assertEqual(1, response['alert_customer_id'])

    def test_create_alert_should_return_400_when_alert_customer_id_is_missing(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
        }
        response = self._subject.create('/api/v2/alerts', body)
        self.assertEqual(400, response.status_code)

    def test_create_alert_should_return_403_when_user_has_no_permission_to_alert(self):
        user = self._subject.create_dummy_user()
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = user.create('/api/v2/alerts', body)
        self.assertEqual(403, response.status_code)

    def test_create_alert_should_return_field_classification_id_null_when_not_provided(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create('/api/v2/alerts', body).json()
        self.assertIsNone(response['alert_classification_id'])

    def test_alerts_with_filter_alerts_assets_should_not_fail(self):
        response = self._subject.get('/api/v2/alerts', query_parameters={'alert_assets': 'some assert name'})
        self.assertEqual(200, response.status_code)

    def test_alerts_filter_with_filter_alert_iocs_should_not_fail(self):
        response = self._subject.get('api/v2/alerts', query_parameters={'alert_iocs': 'some ioc value'})
        self.assertEqual(200, response.status_code)

    def test_get_alerts_filter_should_show_newly_created_alert_for_administrator(self):
        alert_title = 'title_test'
        body = {
            'alert_title': alert_title,
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1
        }
        self._subject.create('/alerts/add', body)
        response = self._subject.get('/api/v2/alerts', query_parameters={'alert_title': alert_title}).json()
        self.assertEqual(1, response['total'])

    def test_get_alerts_should_return_field_data(self):
        response = self._subject.get('/api/v2/alerts').json()
        self.assertEqual([], response['data'])

    def test_merge_alert_into_a_case_should_not_fail(self):
        case_identifier = self._subject.create_dummy_case()
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1
        }
        response = self._subject.create('/alerts/add', body).json()
        alert_identifier = response['data']['alert_id']
        body = {
            'target_case_id': case_identifier,
            'iocs_import_list': [],
            'assets_import_list': []
        }
        response = self._subject.create(f'/alerts/merge/{alert_identifier}', body)
        # TODO should be 201
        self.assertEqual(200, response.status_code)

    def test_batch_escalate_should_correlate_matching_iocs_into_a_single_case_ioc(self):
        ioc_value = '203.0.113.10'
        asset_name = 'shared-account'

        alert_body = {
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
            'alert_assets': [{
                'asset_name': asset_name,
                'asset_description': 'Shared account asset',
                'asset_type_id': 1,
                'asset_ip': '203.0.113.10',
                'asset_domain': '',
                'asset_tags': 'shared'
            }],
            'alert_iocs': [{
                'ioc_value': ioc_value,
                'ioc_description': 'Shared IOC across alerts',
                'ioc_tlp_id': 1,
                'ioc_type_id': 1,
                'ioc_tags': 'shared'
            }]
        }

        first_alert = self._subject.create('/api/v2/alerts', {
            **alert_body,
            'alert_title': 'First alert'
        }).json()
        second_alert = self._subject.create('/api/v2/alerts', {
            **alert_body,
            'alert_title': 'Second alert'
        }).json()

        response = self._subject.create('/alerts/batch/escalate', {
            'alert_ids': f"{first_alert['alert_id']},{second_alert['alert_id']}",
            'iocs_import_list': [first_alert['iocs'][0]['ioc_uuid'], second_alert['iocs'][0]['ioc_uuid']],
            'assets_import_list': [first_alert['assets'][0]['asset_uuid'], second_alert['assets'][0]['asset_uuid']],
            'note': 'Regression coverage for shared IOC correlation',
            'import_as_event': True,
            'case_tags': 'batch-escalation',
            'case_title': 'Batch escalation regression case'
        })

        self.assertEqual(200, response.status_code)

        case_identifier = response.json()['data']['case_id']

        case_iocs = self._subject.get(f'/api/v2/cases/{case_identifier}/iocs').json()
        self.assertEqual(1, case_iocs['total'])

        case_assets = self._subject.get(f'/api/v2/cases/{case_identifier}/assets').json()
        self.assertEqual(1, case_assets['total'])

        timeline = self._subject.get('/case/timeline/events/list', query_parameters={'cid': case_identifier}).json()['data']['timeline']
        self.assertEqual(2, len(timeline))

        event_ioc_ids = set()
        event_asset_ids = set()
        for event in timeline:
            event_data = self._subject.get(f"/api/v2/cases/{case_identifier}/events/{event['event_id']}").json()
            self.assertEqual(1, len(event_data['event_iocs']))
            self.assertEqual(1, len(event_data['event_assets']))
            event_ioc_ids.add(event_data['event_iocs'][0])
            event_asset_ids.add(event_data['event_assets'][0])

        self.assertEqual(1, len(event_ioc_ids))
        self.assertEqual(1, len(event_asset_ids))

    def test_create_customer_should_return_400_when_user_has_customer_alert_right(self):
        group_identifier = self._subject.create_dummy_group([IRIS_PERMISSION_ALERTS_WRITE])
        user = self._subject.create_dummy_user()
        body = {'groups_membership': [group_identifier]}
        self._subject.create(f'/manage/users/{user.get_identifier()}/groups/update', body)

        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = user.create('/api/v2/alerts', body)
        self.assertEqual(400, response.status_code)

    def test_get_alert_should_return_200(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1
        }
        response = self._subject.create('api/v2/alerts', body).json()
        identifier = response['alert_id']
        response = self._subject.get(f'/api/v2/alerts/{identifier}')
        self.assertEqual(200, response.status_code)

    def test_get_alert_should_return_alert_title(self):
        alert_title = 'title_test'
        body = {
            'alert_title': alert_title,
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1
        }
        response = self._subject.create('api/v2/alerts', body).json()
        identifier = response['alert_id']
        response = self._subject.get(f'/api/v2/alerts/{identifier}').json()
        self.assertEqual(alert_title, response['alert_title'])

    def test_get_alert_should_return_alert_uuid(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1
        }
        response = self._subject.create('api/v2/alerts', body).json()
        identifier = response['alert_id']
        uuid = response['alert_uuid']
        response = self._subject.get(f'/api/v2/alerts/{identifier}').json()
        self.assertEqual(uuid, response['alert_uuid'])

    def test_get_alert_should_return_404_when_alert_not_found(self):
        response = self._subject.get(f'/api/v2/alerts/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}')
        self.assertEqual(404, response.status_code)

    def test_get_alert_should_return_403_when_user_has_no_permission_to_read_alert(self):
        user = self._subject.create_dummy_user()
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create('api/v2/alerts', body).json()
        identifier = response['alert_id']
        response = user.get(f'/api/v2/alerts/{identifier}')
        self.assertEqual(403, response.status_code)

    def test_get_alert_should_return_404_when_user_has_no_customer_access(self):
        group_identifier = self._subject.create_dummy_group([IRIS_PERMISSION_ALERTS_READ])
        user = self._subject.create_dummy_user()
        body = {'groups_membership': [group_identifier]}
        self._subject.create(f'/manage/users/{user.get_identifier()}/groups/update', body)

        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create('/api/v2/alerts', body).json()
        identifier = response['alert_id']
        response = user.get(f'/api/v2/alerts/{identifier}')
        self.assertEqual(404, response.status_code)

    def test_update_alert_should_return_200(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1
        }
        response = self._subject.create('api/v2/alerts', body).json()
        identifier = response['alert_id']
        response = self._subject.update(f'/api/v2/alerts/{identifier}', {'alert_title': 'new_title'})
        self.assertEqual(200, response.status_code)

    def test_update_alert_should_return_alert_title(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1
        }
        response = self._subject.create('api/v2/alerts', body).json()
        identifier = response['alert_id']
        alert_title = 'new_title'
        response = self._subject.update(f'/api/v2/alerts/{identifier}', {'alert_title': alert_title}).json()
        self.assertEqual(alert_title, response['alert_title'])

    def test_update_alert_should_return_alert_uuid(self):
        alert_title = 'new_title'
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1
        }
        response = self._subject.create('api/v2/alerts', body).json()
        identifier = response['alert_id']
        uuid = response['alert_uuid']
        response = self._subject.update(f'/api/v2/alerts/{identifier}', {'alert_title': alert_title}).json()
        self.assertEqual(uuid, response['alert_uuid'])

    def test_update_alert_should_return_404_when_alert_not_found(self):
        response = self._subject.update(f'/api/v2/alerts/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}', {'alert_title': 'alert_title'})
        self.assertEqual(404, response.status_code)

    def test_update_alert_should_return_403_when_user_has_no_permission_to_read_alert(self):
        user = self._subject.create_dummy_user()
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create('api/v2/alerts', body).json()
        identifier = response['alert_id']
        response = user.update(f'/api/v2/alerts/{identifier}', {})
        self.assertEqual(403, response.status_code)

    def test_update_alert_should_return_404_when_user_has_no_customer_access(self):
        group_identifier = self._subject.create_dummy_group([IRIS_PERMISSION_ALERTS_WRITE])
        user = self._subject.create_dummy_user()
        body = {'groups_membership': [group_identifier]}
        self._subject.create(f'/manage/users/{user.get_identifier()}/groups/update', body)

        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create('/api/v2/alerts', body).json()
        identifier = response['alert_id']
        response = user.update(f'/api/v2/alerts/{identifier}', {'alert_title': 'new_title'})
        self.assertEqual(404, response.status_code)

    def test_update_alert_should_update_alert_context(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1
        }
        response = self._subject.create('api/v2/alerts', body).json()
        identifier = response['alert_id']
        alert_context = {'context_key': 'key'}
        response = self._subject.update(f'/api/v2/alerts/{identifier}', {'alert_context': alert_context}).json()
        self.assertEqual(alert_context, response['alert_context'])

    def test_update_alert_should_update_alert_source_content(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1
        }
        response = self._subject.create('api/v2/alerts', body).json()
        identifier = response['alert_id']
        alert_source_content = {
            '_id': '603f704aaf7417985bbf3b22',
            'contextId': '206e2965-6533-48a6-ba9e-794364a84bf9',
            'description': 'Contoso user performed 11 suspicious activities MITRE'
        }
        response = self._subject.update(f'/api/v2/alerts/{identifier}', {'alert_source_content': alert_source_content}).json()
        self.assertEqual(alert_source_content, response['alert_source_content'])

    def test_create_alert_should_return_asset_name_when_we_add_asset(self):
        asset_name = 'My super asset'
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
            'alert_assets': [{
            'asset_name': asset_name,
            'asset_description': 'Asset description',
            'asset_type_id': 1,
            'asset_ip': '1.1.1.1',
            'asset_domain': '',
            'asset_tags': 'tag1,tag2',
            }]
        }
        response = self._subject.create('/api/v2/alerts', body).json()
        self.assertEqual(asset_name, response['assets'][0]['asset_name'])

    def test_create_alert_should_return_ioc_value_when_we_add_ioc(self):
        ioc_value = 'Tarzan 5'
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
            'alert_iocs': [{
                'ioc_value': ioc_value,
                'ioc_description': 'description of Tarzan',
                'ioc_tlp_id': 1,
                'ioc_type_id': 2,
                'ioc_tags': 'tag1,tag2',
            }]
        }
        response = self._subject.create('/api/v2/alerts', body).json()
        self.assertEqual(ioc_value, response['iocs'][0]['ioc_value'])

    def test_delete_alert_should_return_204(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1
        }
        response = self._subject.create('api/v2/alerts', body).json()
        identifier = response['alert_id']
        response = self._subject.delete(f'/api/v2/alerts/{identifier}')
        self.assertEqual(204, response.status_code)

    def test_delete_alert_should_return_404_when_alert_not_found(self):
        response = self._subject.delete(f'/api/v2/alerts/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}')
        self.assertEqual(404, response.status_code)

    def test_delete_alert_should_return_403_when_user_has_no_permission_to_delete_alert(self):
        user = self._subject.create_dummy_user()
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1
        }
        response = self._subject.create('api/v2/alerts', body).json()
        identifier = response['alert_id']
        response = user.delete(f'/api/v2/alerts/{identifier}')
        self.assertEqual(403, response.status_code)

    def test_delete_alert_should_return_404_when_user_has_no_customer_access(self):
        group_identifier = self._subject.create_dummy_group([IRIS_PERMISSION_ALERTS_DELETE])
        user = self._subject.create_dummy_user()
        body = {'groups_membership': [group_identifier]}
        self._subject.create(f'/manage/users/{user.get_identifier()}/groups/update', body)

        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create('/api/v2/alerts', body).json()
        identifier = response['alert_id']
        response = user.delete(f'/api/v2/alerts/{identifier}')
        self.assertEqual(404, response.status_code)

    def test_get_alert_should_return_404_after_delete_alert(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1
        }
        response = self._subject.create('api/v2/alerts', body).json()
        identifier = response['alert_id']
        self._subject.delete(f'/api/v2/alerts/{identifier}')
        response = self._subject.get(f'/api/v2/alerts/{identifier}')
        self.assertEqual(404, response.status_code)

    def test_get_related_alerts_should_return_200(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1
        }
        response = self._subject.create('api/v2/alerts', body).json()
        identifier = response['alert_id']
        response = self._subject.get(f'/api/v2/alerts/{identifier}/related-alerts')
        self.assertEqual(200, response.status_code)

    def test_get_related_alerts_should_return_404_when_alert_not_found(self):
        response = self._subject.get(f'/api/v2/alerts/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}/related-alerts')
        self.assertEqual(404, response.status_code)

    def test_get_related_alerts_should_return_403_when_user_has_no_permission_to_get_alert(self):
        user = self._subject.create_dummy_user()
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1
        }
        response = self._subject.create('api/v2/alerts', body).json()
        identifier = response['alert_id']
        response = user.get(f'/api/v2/alerts/{identifier}/related-alerts')
        self.assertEqual(403, response.status_code)

    def test_get_related_alerts_should_return_404_when_user_has_no_customer_access(self):
        body = {
            'group_name': 'Customer read',
            'group_description': 'Group with customers can read alert',
            'group_permissions': [IRIS_PERMISSION_ALERTS_READ]
        }
        response = self._subject.create('/manage/groups/add', body).json()
        group_identifier = response['data']['group_id']
        user = self._subject.create_dummy_user()
        body = {'groups_membership': [group_identifier]}
        self._subject.create(f'/manage/users/{user.get_identifier()}/groups/update', body)

        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create('/api/v2/alerts', body).json()
        identifier = response['alert_id']
        response = user.get(f'/api/v2/alerts/{identifier}/related-alerts')
        self.assertEqual(404, response.status_code)

    def test_create_alert_should_add_closed_case_context_tag_on_match(self):
        case_identifier = self._subject.create_dummy_case()
        self._subject.create(f'/api/v2/cases/{case_identifier}/assets', {
            'asset_type_id': 1,
            'asset_name': 'host-closed-case'
        })
        self._subject.create(f'/api/v2/cases/{case_identifier}/iocs', {
            'ioc_type_id': 1,
            'ioc_tlp_id': 2,
            'ioc_value': '198.51.100.12',
            'ioc_description': 'closed case indicator',
            'ioc_tags': 'historic'
        })
        self._subject.create(f'/manage/cases/close/{case_identifier}', {})

        response = self._subject.create('/api/v2/alerts', {
            'alert_title': 'closed context alert',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
            'alert_assets': [{
                'asset_name': 'host-closed-case',
                'asset_description': 'Matching closed case asset',
                'asset_type_id': 1,
                'asset_ip': '198.51.100.12',
                'asset_domain': '',
                'asset_tags': 'match'
            }],
            'alert_iocs': [{
                'ioc_value': '198.51.100.12',
                'ioc_description': 'Matching closed case IOC',
                'ioc_tlp_id': 1,
                'ioc_type_id': 1,
                'ioc_tags': 'match'
            }]
        }).json()

        self.assertIn('seen-in-closed-case', response['alert_tags'])
        self.assertIn('closed_case_hits', response['alert_context'])
        self.assertEqual(case_identifier, response['alert_context']['closed_case_hits'][0]['case_id'])

    def test_get_case_correlation_should_return_open_and_closed_matches(self):
        open_case_identifier = self._subject.create_dummy_case()
        closed_case_identifier = self._subject.create_dummy_case()

        self._subject.create(f'/api/v2/cases/{open_case_identifier}/assets', {
            'asset_type_id': 1,
            'asset_name': 'shared-host'
        })
        self._subject.create(f'/api/v2/cases/{closed_case_identifier}/iocs', {
            'ioc_type_id': 1,
            'ioc_tlp_id': 2,
            'ioc_value': '203.0.113.42',
            'ioc_description': 'Shared IOC',
            'ioc_tags': 'shared'
        })
        self._subject.create(f'/manage/cases/close/{closed_case_identifier}', {})

        alert = self._subject.create('/api/v2/alerts', {
            'alert_title': 'correlation alert',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
            'alert_assets': [{
                'asset_name': 'shared-host',
                'asset_description': 'shared host',
                'asset_type_id': 1,
                'asset_ip': '203.0.113.10',
                'asset_domain': '',
                'asset_tags': 'shared'
            }],
            'alert_iocs': [{
                'ioc_value': '203.0.113.42',
                'ioc_description': 'shared ioc',
                'ioc_tlp_id': 1,
                'ioc_type_id': 1,
                'ioc_tags': 'shared'
            }]
        }).json()

        response = self._subject.get(f"/api/v2/alerts/{alert['alert_id']}/case-correlation").json()
        self.assertTrue(response['has_open_match'])
        self.assertTrue(response['has_closed_match'])

        open_case_ids = [item['case_id'] for item in response['open_case_matches']]
        closed_case_ids = [item['case_id'] for item in response['closed_case_matches']]
        self.assertIn(open_case_identifier, open_case_ids)
        self.assertIn(closed_case_identifier, closed_case_ids)

    def test_merge_correlation_should_merge_alert_into_multiple_open_cases(self):
        case_identifier_1 = self._subject.create_dummy_case()
        case_identifier_2 = self._subject.create_dummy_case()

        self._subject.create(f'/api/v2/cases/{case_identifier_1}/assets', {
            'asset_type_id': 1,
            'asset_name': 'multi-case-host'
        })
        self._subject.create(f'/api/v2/cases/{case_identifier_2}/iocs', {
            'ioc_type_id': 1,
            'ioc_tlp_id': 2,
            'ioc_value': '192.0.2.55',
            'ioc_description': 'Multi case IOC',
            'ioc_tags': 'multi'
        })

        alert = self._subject.create('/api/v2/alerts', {
            'alert_title': 'multi case merge',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
            'alert_assets': [{
                'asset_name': 'multi-case-host',
                'asset_description': 'match host',
                'asset_type_id': 1,
                'asset_ip': '192.0.2.55',
                'asset_domain': '',
                'asset_tags': 'multi'
            }],
            'alert_iocs': [{
                'ioc_value': '192.0.2.55',
                'ioc_description': 'match ioc',
                'ioc_tlp_id': 1,
                'ioc_type_id': 1,
                'ioc_tags': 'multi'
            }]
        }).json()

        response = self._subject.create(f"/api/v2/alerts/{alert['alert_id']}/merge-correlation", {
            'target_case_ids': [case_identifier_1, case_identifier_2],
            'import_as_event': False,
            'case_tags': 'correlation-merge',
            'note': 'Analyst accepted case matches'
        }).json()

        self.assertEqual(sorted([case_identifier_1, case_identifier_2]), sorted(response['merged_case_ids']))

        updated_alert = self._subject.get(f"/api/v2/alerts/{alert['alert_id']}").json()
        linked_case_ids = sorted(updated_alert['cases'])
        self.assertEqual(sorted([case_identifier_1, case_identifier_2]), linked_case_ids)

    def test_connected_preview_and_escalate_should_merge_all_connected_alerts(self):
        alert_one = self._subject.create('/api/v2/alerts', {
            'alert_title': 'entity pivot alert one',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
            'alert_iocs': [{
                'ioc_value': '203.0.113.200',
                'ioc_description': 'entity pivot ioc',
                'ioc_tlp_id': 1,
                'ioc_type_id': 1,
                'ioc_tags': 'pivot'
            }]
        }).json()

        alert_two = self._subject.create('/api/v2/alerts', {
            'alert_title': 'entity pivot alert two',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
            'alert_iocs': [{
                'ioc_value': '203.0.113.200',
                'ioc_description': 'entity pivot ioc',
                'ioc_tlp_id': 1,
                'ioc_type_id': 1,
                'ioc_tags': 'pivot'
            }]
        }).json()

        preview = self._subject.create('/api/v2/alerts/connected/preview', {
            'customer_id': 1,
            'entity': {
                'kind': 'ioc',
                'ioc_value': '203.0.113.200',
                'ioc_type_id': 1
            },
            'max_alerts': 100
        }).json()

        self.assertEqual(2, preview['connected_alert_count'])
        self.assertIn(alert_one['alert_id'], preview['connected_alert_ids'])
        self.assertIn(alert_two['alert_id'], preview['connected_alert_ids'])

        escalated = self._subject.create('/api/v2/alerts/connected/escalate', {
            'customer_id': 1,
            'entity': {
                'kind': 'ioc',
                'ioc_value': '203.0.113.200',
                'ioc_type_id': 1
            },
            'connected_alert_ids': preview['connected_alert_ids'],
            'case_title': 'Entity Pivot Case',
            'case_tags': 'entity-pivot',
            'import_as_event': False
        }).json()

        self.assertIsNotNone(escalated['case_id'])
        self.assertEqual(2, len(escalated['merged_alert_ids']))

        case_identifier = escalated['case_id']
        alert_one_updated = self._subject.get(f"/api/v2/alerts/{alert_one['alert_id']}").json()
        alert_two_updated = self._subject.get(f"/api/v2/alerts/{alert_two['alert_id']}").json()
        self.assertIn(case_identifier, alert_one_updated['cases'])
        self.assertIn(case_identifier, alert_two_updated['cases'])
