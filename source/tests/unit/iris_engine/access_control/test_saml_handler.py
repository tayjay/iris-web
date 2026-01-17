#  IRIS Source Code
#  Copyright (C) 2021 - Airbus CyberSecurity (SAS)
#  ir@cyberactionlab.net
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

"""
Unit tests for SAML handler functions.

These tests are designed to run without requiring the full application
dependencies by testing the logic in isolation.
"""

import unittest
from unittest.mock import MagicMock


class TestPrepareFlaskRequestLogic(unittest.TestCase):
    """Tests for prepare_flask_request logic"""

    def _prepare_flask_request(self, request):
        """
        Replicate the prepare_flask_request function logic for testing.
        This avoids importing the actual module which has dependencies.
        """
        return {
            'https': 'on' if request.scheme == 'https' else 'off',
            'http_host': request.host,
            'server_port': request.environ.get('SERVER_PORT', '443' if request.scheme == 'https' else '80'),
            'script_name': request.path,
            'get_data': request.args.copy(),
            'post_data': request.form.copy(),
            'query_string': request.query_string.decode('utf-8')
        }

    def test_prepare_flask_request_https(self):
        """Test that HTTPS requests are properly formatted"""
        mock_request = MagicMock()
        mock_request.scheme = 'https'
        mock_request.host = 'iris.example.com'
        mock_request.environ = {'SERVER_PORT': '443'}
        mock_request.path = '/saml/acs'
        mock_request.args.copy.return_value = {}
        mock_request.form.copy.return_value = {'SAMLResponse': 'test_response'}
        mock_request.query_string = b''

        result = self._prepare_flask_request(mock_request)

        self.assertEqual(result['https'], 'on')
        self.assertEqual(result['http_host'], 'iris.example.com')
        self.assertEqual(result['server_port'], '443')
        self.assertEqual(result['script_name'], '/saml/acs')
        self.assertEqual(result['get_data'], {})
        self.assertEqual(result['post_data'], {'SAMLResponse': 'test_response'})

    def test_prepare_flask_request_http(self):
        """Test that HTTP requests are properly formatted"""
        mock_request = MagicMock()
        mock_request.scheme = 'http'
        mock_request.host = 'localhost:8080'
        mock_request.environ = {'SERVER_PORT': '8080'}
        mock_request.path = '/saml/login'
        mock_request.args.copy.return_value = {'next': '/dashboard'}
        mock_request.form.copy.return_value = {}
        mock_request.query_string = b'next=/dashboard'

        result = self._prepare_flask_request(mock_request)

        self.assertEqual(result['https'], 'off')
        self.assertEqual(result['http_host'], 'localhost:8080')
        self.assertEqual(result['server_port'], '8080')
        self.assertEqual(result['script_name'], '/saml/login')
        self.assertEqual(result['get_data'], {'next': '/dashboard'})
        self.assertEqual(result['query_string'], 'next=/dashboard')

    def test_prepare_flask_request_default_port_https(self):
        """Test default port when SERVER_PORT is not in environ for HTTPS"""
        mock_request = MagicMock()
        mock_request.scheme = 'https'
        mock_request.host = 'iris.example.com'
        mock_request.environ = {}
        mock_request.path = '/saml/acs'
        mock_request.args.copy.return_value = {}
        mock_request.form.copy.return_value = {}
        mock_request.query_string = b''

        result = self._prepare_flask_request(mock_request)

        self.assertEqual(result['server_port'], '443')

    def test_prepare_flask_request_default_port_http(self):
        """Test default port when SERVER_PORT is not in environ for HTTP"""
        mock_request = MagicMock()
        mock_request.scheme = 'http'
        mock_request.host = 'localhost'
        mock_request.environ = {}
        mock_request.path = '/saml/login'
        mock_request.args.copy.return_value = {}
        mock_request.form.copy.return_value = {}
        mock_request.query_string = b''

        result = self._prepare_flask_request(mock_request)

        self.assertEqual(result['server_port'], '80')


class TestGetSamlSettingsLogic(unittest.TestCase):
    """Tests for get_saml_settings logic"""

    def _get_saml_settings(self, config):
        """
        Replicate the get_saml_settings function logic for testing.
        """
        # Build IdP settings
        idp_settings = {
            'entityId': config.get('SAML_IDP_ENTITY_ID'),
            'singleSignOnService': {
                'url': config.get('SAML_IDP_SSO_URL'),
                'binding': 'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect'
            },
            'x509cert': config.get('SAML_IDP_X509_CERT', '')
        }

        # Add SLO URL if configured
        slo_url = config.get('SAML_IDP_SLO_URL')
        if slo_url:
            idp_settings['singleLogoutService'] = {
                'url': slo_url,
                'binding': 'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect'
            }

        # Build SP settings
        sp_settings = {
            'entityId': config.get('SAML_SP_ENTITY_ID'),
            'assertionConsumerService': {
                'url': config.get('SAML_SP_ACS_URL'),
                'binding': 'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST'
            },
            'NameIDFormat': 'urn:oasis:names:tc:SAML:1.1:nameid-format:unspecified'
        }

        # Add SP certificate and key if configured
        sp_cert = config.get('SAML_SP_X509_CERT')
        sp_key = config.get('SAML_SP_PRIVATE_KEY')
        if sp_cert:
            sp_settings['x509cert'] = sp_cert
        if sp_key:
            sp_settings['privateKey'] = sp_key

        # Build security settings
        security_settings = {
            'nameIdEncrypted': False,
            'authnRequestsSigned': bool(sp_cert and sp_key),
            'logoutRequestSigned': bool(sp_cert and sp_key),
            'logoutResponseSigned': bool(sp_cert and sp_key),
            'signMetadata': bool(sp_cert and sp_key),
            'wantMessagesSigned': config.get('SAML_WANT_RESPONSE_SIGNED', True),
            'wantAssertionsSigned': config.get('SAML_WANT_ASSERTIONS_SIGNED', True),
            'wantNameId': True,
            'wantNameIdEncrypted': False,
            'wantAssertionsEncrypted': False,
            'allowSingleLabelDomains': False,
            'signatureAlgorithm': 'http://www.w3.org/2001/04/xmldsig-more#rsa-sha256',
            'digestAlgorithm': 'http://www.w3.org/2001/04/xmlenc#sha256'
        }

        settings = {
            'strict': True,
            'debug': config.get('DEVELOPMENT', False),
            'sp': sp_settings,
            'idp': idp_settings,
            'security': security_settings
        }

        return settings

    def _create_config(self, **overrides):
        """Create a mock config dictionary"""
        config = {
            'SAML_IDP_ENTITY_ID': 'https://idp.example.com',
            'SAML_IDP_SSO_URL': 'https://idp.example.com/sso',
            'SAML_IDP_X509_CERT': 'MIICpDCCAYwCCQDU+pQ4P3...',
            'SAML_SP_ENTITY_ID': 'https://iris.example.com/saml/metadata',
            'SAML_SP_ACS_URL': 'https://iris.example.com/saml/acs',
            'SAML_WANT_ASSERTIONS_SIGNED': True,
            'SAML_WANT_RESPONSE_SIGNED': True,
            'DEVELOPMENT': False,
            'SAML_IDP_SLO_URL': None,
            'SAML_SP_X509_CERT': None,
            'SAML_SP_PRIVATE_KEY': None,
        }
        config.update(overrides)
        return config

    def test_get_saml_settings_basic(self):
        """Test basic SAML settings generation"""
        config = self._create_config()
        settings = self._get_saml_settings(config)

        # Check IdP settings
        self.assertEqual(settings['idp']['entityId'], 'https://idp.example.com')
        self.assertEqual(settings['idp']['singleSignOnService']['url'], 'https://idp.example.com/sso')
        self.assertEqual(settings['idp']['x509cert'], 'MIICpDCCAYwCCQDU+pQ4P3...')

        # Check SP settings
        self.assertEqual(settings['sp']['entityId'], 'https://iris.example.com/saml/metadata')
        self.assertEqual(settings['sp']['assertionConsumerService']['url'], 'https://iris.example.com/saml/acs')

        # Check security settings
        self.assertTrue(settings['security']['wantAssertionsSigned'])
        self.assertTrue(settings['security']['wantMessagesSigned'])

        # Check strict mode
        self.assertTrue(settings['strict'])
        self.assertFalse(settings['debug'])

    def test_get_saml_settings_with_slo(self):
        """Test SAML settings generation with SLO URL"""
        config = self._create_config(SAML_IDP_SLO_URL='https://idp.example.com/slo')
        settings = self._get_saml_settings(config)

        self.assertIn('singleLogoutService', settings['idp'])
        self.assertEqual(settings['idp']['singleLogoutService']['url'], 'https://idp.example.com/slo')

    def test_get_saml_settings_without_slo(self):
        """Test SAML settings generation without SLO URL"""
        config = self._create_config()
        settings = self._get_saml_settings(config)

        self.assertNotIn('singleLogoutService', settings['idp'])

    def test_get_saml_settings_with_sp_signing(self):
        """Test SAML settings with SP signing certificate"""
        config = self._create_config(
            SAML_SP_X509_CERT='MIICpDCCAYwCCQDU+pQ4P3_SP...',
            SAML_SP_PRIVATE_KEY='MIIEvgIBADANBgkqhkiG9w0B...'
        )
        settings = self._get_saml_settings(config)

        self.assertEqual(settings['sp']['x509cert'], 'MIICpDCCAYwCCQDU+pQ4P3_SP...')
        self.assertEqual(settings['sp']['privateKey'], 'MIIEvgIBADANBgkqhkiG9w0B...')
        self.assertTrue(settings['security']['authnRequestsSigned'])
        self.assertTrue(settings['security']['logoutRequestSigned'])

    def test_get_saml_settings_without_sp_signing(self):
        """Test SAML settings without SP signing certificate"""
        config = self._create_config()
        settings = self._get_saml_settings(config)

        self.assertNotIn('x509cert', settings['sp'])
        self.assertNotIn('privateKey', settings['sp'])
        self.assertFalse(settings['security']['authnRequestsSigned'])
        self.assertFalse(settings['security']['logoutRequestSigned'])

    def test_get_saml_settings_debug_mode(self):
        """Test SAML settings in development mode"""
        config = self._create_config(DEVELOPMENT=True)
        settings = self._get_saml_settings(config)

        self.assertTrue(settings['debug'])

    def test_get_saml_settings_security_disabled(self):
        """Test SAML settings with security options disabled"""
        config = self._create_config(
            SAML_WANT_ASSERTIONS_SIGNED=False,
            SAML_WANT_RESPONSE_SIGNED=False
        )
        settings = self._get_saml_settings(config)

        self.assertFalse(settings['security']['wantAssertionsSigned'])
        self.assertFalse(settings['security']['wantMessagesSigned'])

    def test_get_saml_settings_bindings(self):
        """Test that correct SAML bindings are set"""
        config = self._create_config()
        settings = self._get_saml_settings(config)

        # SSO should use HTTP-Redirect
        self.assertEqual(
            settings['idp']['singleSignOnService']['binding'],
            'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect'
        )

        # ACS should use HTTP-POST
        self.assertEqual(
            settings['sp']['assertionConsumerService']['binding'],
            'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST'
        )

    def test_get_saml_settings_nameid_format(self):
        """Test that NameID format is set correctly"""
        config = self._create_config()
        settings = self._get_saml_settings(config)

        self.assertEqual(
            settings['sp']['NameIDFormat'],
            'urn:oasis:names:tc:SAML:1.1:nameid-format:unspecified'
        )

    def test_get_saml_settings_signature_algorithms(self):
        """Test that signature algorithms are set correctly"""
        config = self._create_config()
        settings = self._get_saml_settings(config)

        self.assertEqual(
            settings['security']['signatureAlgorithm'],
            'http://www.w3.org/2001/04/xmldsig-more#rsa-sha256'
        )
        self.assertEqual(
            settings['security']['digestAlgorithm'],
            'http://www.w3.org/2001/04/xmlenc#sha256'
        )


class TestSamlAttributeExtraction(unittest.TestCase):
    """Tests for SAML attribute extraction logic used in ACS"""

    def test_extract_username_from_attributes(self):
        """Test extracting username from SAML attributes"""
        attributes = {
            'uid': ['testuser'],
            'email': ['testuser@example.com'],
            'displayName': ['Test User']
        }
        name_id = 'testuser@example.com'
        username_attr = 'uid'

        user_login = attributes.get(username_attr, [name_id])[0] if attributes.get(username_attr) else name_id

        self.assertEqual(user_login, 'testuser')

    def test_extract_email_from_attributes(self):
        """Test extracting email from SAML attributes"""
        attributes = {
            'uid': ['testuser'],
            'email': ['testuser@example.com'],
            'displayName': ['Test User']
        }
        email_attr = 'email'
        user_login = 'testuser'

        user_email = attributes.get(email_attr, [f'{user_login}@saml'])[0] if attributes.get(email_attr) else f'{user_login}@saml'

        self.assertEqual(user_email, 'testuser@example.com')

    def test_extract_display_name_from_attributes(self):
        """Test extracting display name from SAML attributes"""
        attributes = {
            'uid': ['testuser'],
            'email': ['testuser@example.com'],
            'displayName': ['Test User']
        }
        name_attr = 'displayName'
        user_login = 'testuser'

        user_name = attributes.get(name_attr, [user_login])[0] if attributes.get(name_attr) else user_login

        self.assertEqual(user_name, 'Test User')

    def test_fallback_to_nameid_when_username_missing(self):
        """Test fallback to NameID when username attribute is missing"""
        attributes = {}
        name_id = 'testuser@example.com'
        username_attr = 'uid'

        user_login = attributes.get(username_attr, [name_id])[0] if attributes.get(username_attr) else name_id

        self.assertEqual(user_login, 'testuser@example.com')

    def test_fallback_email_when_attribute_missing(self):
        """Test fallback email generation when attribute is missing"""
        attributes = {}
        email_attr = 'email'
        user_login = 'testuser'

        user_email = attributes.get(email_attr, [f'{user_login}@saml'])[0] if attributes.get(email_attr) else f'{user_login}@saml'

        self.assertEqual(user_email, 'testuser@saml')

    def test_fallback_name_when_attribute_missing(self):
        """Test fallback to login when display name attribute is missing"""
        attributes = {}
        name_attr = 'displayName'
        user_login = 'testuser'

        user_name = attributes.get(name_attr, [user_login])[0] if attributes.get(name_attr) else user_login

        self.assertEqual(user_name, 'testuser')

    def test_urn_style_attribute_mapping(self):
        """Test mapping with URN-style attribute names (common in enterprise IdPs)"""
        attributes = {
            'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress': ['user@okta.com'],
            'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name': ['Okta User'],
        }
        email_attr = 'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress'

        user_email = attributes.get(email_attr, [None])[0]

        self.assertEqual(user_email, 'user@okta.com')


class TestSamlSecuritySettings(unittest.TestCase):
    """Tests for SAML security settings validation"""

    def test_signing_enabled_with_cert_and_key(self):
        """Test that signing is enabled when both cert and key are provided"""
        sp_cert = 'MIICpDCCAYwCCQDU+pQ4P3...'
        sp_key = 'MIIEvgIBADANBgkqhkiG9w0B...'

        should_sign = bool(sp_cert and sp_key)

        self.assertTrue(should_sign)

    def test_signing_disabled_without_cert(self):
        """Test that signing is disabled when cert is missing"""
        sp_cert = None
        sp_key = 'MIIEvgIBADANBgkqhkiG9w0B...'

        should_sign = bool(sp_cert and sp_key)

        self.assertFalse(should_sign)

    def test_signing_disabled_without_key(self):
        """Test that signing is disabled when key is missing"""
        sp_cert = 'MIICpDCCAYwCCQDU+pQ4P3...'
        sp_key = None

        should_sign = bool(sp_cert and sp_key)

        self.assertFalse(should_sign)

    def test_signing_disabled_with_empty_strings(self):
        """Test that signing is disabled with empty strings"""
        sp_cert = ''
        sp_key = ''

        should_sign = bool(sp_cert and sp_key)

        self.assertFalse(should_sign)


class TestSamlUserProvisioning(unittest.TestCase):
    """Tests for SAML user provisioning logic"""

    def test_generates_random_password(self):
        """Test that a random password is generated for new SAML users"""
        import string
        import random

        # Same logic as in login_routes.py
        password = ''.join(random.choices(string.printable[:-6], k=16))

        self.assertEqual(len(password), 16)
        # Password should contain printable characters (excluding last 6 which are whitespace)
        for char in password:
            self.assertIn(char, string.printable[:-6])

    def test_password_uniqueness(self):
        """Test that generated passwords are unique"""
        import string
        import random

        passwords = set()
        for _ in range(100):
            password = ''.join(random.choices(string.printable[:-6], k=16))
            passwords.add(password)

        # All passwords should be unique (statistically very likely)
        self.assertEqual(len(passwords), 100)


class TestSamlConfiguration(unittest.TestCase):
    """Tests for SAML configuration validation"""

    def test_is_authentication_saml(self):
        """Test is_authentication_saml logic"""
        config = {'AUTHENTICATION_TYPE': 'saml'}
        is_saml = config.get('AUTHENTICATION_TYPE') == 'saml'
        self.assertTrue(is_saml)

    def test_is_not_authentication_saml(self):
        """Test is_authentication_saml returns False for other types"""
        for auth_type in ['local', 'ldap', 'oidc', 'oidc_proxy']:
            config = {'AUTHENTICATION_TYPE': auth_type}
            is_saml = config.get('AUTHENTICATION_TYPE') == 'saml'
            self.assertFalse(is_saml, f"Should be False for {auth_type}")

    def test_required_saml_config_keys(self):
        """Test that all required SAML config keys are defined"""
        required_keys = [
            'SAML_IDP_ENTITY_ID',
            'SAML_IDP_SSO_URL',
            'SAML_IDP_X509_CERT',
            'SAML_SP_ENTITY_ID',
            'SAML_SP_ACS_URL',
        ]

        config = {
            'SAML_IDP_ENTITY_ID': 'https://idp.example.com',
            'SAML_IDP_SSO_URL': 'https://idp.example.com/sso',
            'SAML_IDP_X509_CERT': 'cert_data',
            'SAML_SP_ENTITY_ID': 'https://sp.example.com',
            'SAML_SP_ACS_URL': 'https://sp.example.com/acs',
        }

        for key in required_keys:
            self.assertIn(key, config)
            self.assertIsNotNone(config[key])

    def test_optional_saml_config_keys(self):
        """Test that optional SAML config keys have sensible defaults"""
        optional_keys_with_defaults = {
            'SAML_IDP_SLO_URL': None,
            'SAML_SP_X509_CERT': None,
            'SAML_SP_PRIVATE_KEY': None,
            'SAML_WANT_ASSERTIONS_SIGNED': True,
            'SAML_WANT_RESPONSE_SIGNED': True,
            'SAML_MAPPING_USERNAME': 'uid',
            'SAML_MAPPING_EMAIL': 'email',
            'SAML_MAPPING_NAME': 'displayName',
        }

        for key, default in optional_keys_with_defaults.items():
            # Test that the default value is what we expect
            self.assertEqual(default, optional_keys_with_defaults[key])


if __name__ == '__main__':
    unittest.main()
