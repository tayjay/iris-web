#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock
from unittest.mock import patch

from app.datamgmt.alerts import alerts_db


class TestAlertCorrelation(TestCase):

    def test_get_alert_case_matches_should_split_open_and_closed(self):
        alert = SimpleNamespace(
            alert_id=101,
            alert_customer_id=1,
            assets=[SimpleNamespace(asset_name='host-1', asset_type_id=1)],
            iocs=[SimpleNamespace(ioc_value='203.0.113.5', ioc_type_id=2)]
        )

        asset_query = MagicMock()
        asset_query.join.return_value.filter.return_value.all.return_value = [
            (10, 'host-1', 1, 'Open case', None)
        ]
        ioc_query = MagicMock()
        ioc_query.join.return_value.filter.return_value.all.return_value = [
            (20, '203.0.113.5', 2, 'Closed case', '2026-04-21T00:00:00')
        ]

        with patch.object(alerts_db.db.session, 'query', side_effect=[asset_query, ioc_query]):
            result = alerts_db.get_alert_case_matches(alert)

        self.assertTrue(result['has_open_match'])
        self.assertTrue(result['has_closed_match'])
        self.assertEqual(10, result['open_case_matches'][0]['case_id'])
        self.assertEqual(20, result['closed_case_matches'][0]['case_id'])

    def test_enrich_alert_with_closed_case_context_should_add_tag_and_deduplicate(self):
        alert = SimpleNamespace(alert_tags='triage', alert_context={})
        closed_matches = [{
            'case_id': 99,
            'case_name': 'Historic case',
            'matched_assets': [{'asset_name': 'host-1', 'asset_type_id': 1}],
            'matched_iocs': [{'ioc_value': '198.51.100.5', 'ioc_type_id': 2}]
        }]

        alerts_db.enrich_alert_with_closed_case_context(alert, closed_matches)
        alerts_db.enrich_alert_with_closed_case_context(alert, closed_matches)

        self.assertIn('seen-in-closed-case', alert.alert_tags)
        self.assertIn('closed_case_hits', alert.alert_context)
        self.assertEqual(2, len(alert.alert_context['closed_case_hits']))

    def test_get_connected_open_alert_ids_should_return_alert_identifiers(self):
        query_mock = MagicMock()
        query_mock.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            (11,),
            (12,)
        ]

        with patch.object(alerts_db, '_get_open_alerts_status_identifiers', return_value=[1, 2]), patch.object(
            alerts_db.db.session,
            'query',
            return_value=query_mock,
        ):
            result = alerts_db.get_connected_open_alert_ids(
                1,
                {
                    'kind': 'ioc',
                    'ioc_value': '203.0.113.8',
                    'ioc_type_id': 1
                },
                max_alerts=25
            )

        self.assertEqual([11, 12], result)

    def test_get_closed_case_context_for_entity_should_return_asset_context(self):
        query_mock = MagicMock()
        query_mock.join.return_value.filter.return_value.limit.return_value.all.return_value = [
            (44, 'Closed Case', 'host-2', 1)
        ]

        with patch.object(alerts_db.db.session, 'query', return_value=query_mock):
            result = alerts_db.get_closed_case_context_for_entity(
                1,
                {
                    'kind': 'asset',
                    'asset_name': 'host-2',
                    'asset_type_id': 1
                }
            )

        self.assertEqual(1, len(result))
        self.assertEqual(44, result[0]['case_id'])
        self.assertEqual('asset', result[0]['match_kind'])


if __name__ == '__main__':
    import unittest
    unittest.main(verbosity=2)
