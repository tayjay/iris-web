#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock
from unittest.mock import patch

from app.blueprints.rest.case import case_ioc_routes
from app.datamgmt.alerts import alerts_db
from app.datamgmt.case import case_iocs_db


class TestCaseInsensitiveEntityMatching(TestCase):

    def test_case_iocs_db_exists_uses_lower_comparison_when_enabled(self):
        ioc = SimpleNamespace(case_id=1, ioc_value='User', ioc_type_id=2)
        query_mock = MagicMock()
        query_mock.filter.return_value.first.return_value = None

        with patch.object(case_iocs_db.Ioc, 'query', query_mock), patch.object(
            case_iocs_db,
            'is_case_insensitive_entity_matching_enabled',
            return_value=True,
        ):
            case_iocs_db.case_iocs_db_exists(ioc)

        filter_args = query_mock.filter.call_args[0]
        self.assertTrue(any('lower(ioc.ioc_value)' in str(arg) for arg in filter_args))

    def test_case_iocs_db_exists_uses_exact_comparison_when_disabled(self):
        ioc = SimpleNamespace(case_id=1, ioc_value='User', ioc_type_id=2)
        query_mock = MagicMock()
        query_mock.filter.return_value.first.return_value = None

        with patch.object(case_iocs_db.Ioc, 'query', query_mock), patch.object(
            case_iocs_db,
            'is_case_insensitive_entity_matching_enabled',
            return_value=False,
        ):
            case_iocs_db.case_iocs_db_exists(ioc)

        filter_args = query_mock.filter.call_args[0]
        self.assertFalse(any('lower(ioc.ioc_value)' in str(arg) for arg in filter_args))

    def test_case_ioc_route_existing_lookup_uses_lower_comparison_when_enabled(self):
        query_mock = MagicMock()
        query_mock.filter.return_value.first.return_value = None

        with patch.object(case_ioc_routes.Ioc, 'query', query_mock), patch.object(
            case_ioc_routes,
            'is_case_insensitive_entity_matching_enabled',
            return_value=True,
        ):
            case_ioc_routes._get_existing_ioc(1, 'User', 2)

        filter_args = query_mock.filter.call_args[0]
        self.assertTrue(any('lower(ioc.ioc_value)' in str(arg) for arg in filter_args))

    def test_alert_case_matching_uses_lower_comparison_when_enabled(self):
        ioc_query_mock = MagicMock()
        ioc_query_mock.filter.return_value.first.return_value = None
        asset_query_mock = MagicMock()
        asset_query_mock.filter.return_value.first.return_value = None

        alert_ioc = SimpleNamespace(ioc_value='User', ioc_type_id=2)
        alert_asset = SimpleNamespace(asset_name='User', asset_type_id=7)

        with patch.object(alerts_db.Ioc, 'query', ioc_query_mock), patch.object(
            alerts_db.CaseAssets,
            'query',
            asset_query_mock,
        ), patch.object(
            alerts_db,
            'is_case_insensitive_entity_matching_enabled',
            return_value=True,
        ):
            alerts_db._alerts_get_matching_case_ioc(1, alert_ioc)
            alerts_db._alerts_get_matching_case_asset(1, alert_asset)

        ioc_filter_args = ioc_query_mock.filter.call_args[0]
        self.assertTrue(any('lower(ioc.ioc_value)' in str(arg) for arg in ioc_filter_args))

        asset_filter_expr = asset_query_mock.filter.call_args[0][0]
        self.assertIn('lower(case_assets.asset_name)', str(asset_filter_expr))
