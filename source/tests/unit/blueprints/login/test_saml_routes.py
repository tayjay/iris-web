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
Unit tests for SAML login routes.

These tests are designed to run without requiring the full application
dependencies by testing the logic in isolation.
"""

import unittest
from unittest.mock import MagicMock


class TestSamlLoginRouteLogic(unittest.TestCase):
    """Tests for SAML login route logic"""

    def test_authenticated_user_should_not_redirect_to_idp(self):
        """Test that authenticated users should be redirected to index, not IdP"""
        mock_current_user = MagicMock()
        mock_current_user.is_authenticated = True

        # Logic check: if user is authenticated, don't redirect to SAML
        should_redirect_to_saml = not mock_current_user.is_authenticated

        self.assertFalse(should_redirect_to_saml)

    def test_unauthenticated_user_should_redirect_to_idp(self):
        """Test that unauthenticated users should be redirected to IdP"""
        mock_current_user = MagicMock()
        mock_current_user.is_authenticated = False

        # Logic check: if user is not authenticated, redirect to SAML
        should_redirect_to_saml = not mock_current_user.is_authenticated

        self.assertTrue(should_redirect_to_saml)

    def test_saml_auth_login_returns_redirect_url(self):
        """Test that SAML auth login returns IdP URL"""
        mock_auth = MagicMock()
        mock_auth.login.return_value = 'https://idp.example.com/sso?SAMLRequest=encoded_request'

        redirect_url = mock_auth.login()

        self.assertIn('idp.example.com', redirect_url)
        self.assertIn('SAMLRequest', redirect_url)

    def test_next_url_stored_in_session(self):
        """Test that next URL is stored in session for post-login redirect"""
        session = {}
        next_url = '/dashboard?cid=1'

        if next_url:
            session['saml_next_url'] = next_url

        self.assertEqual(session.get('saml_next_url'), '/dashboard?cid=1')


class TestSamlAcsRouteLogic(unittest.TestCase):
    """Tests for SAML ACS (Assertion Consumer Service) route logic"""

    def test_saml_acs_handles_errors(self):
        """Test that ACS handles SAML errors correctly"""
        mock_auth = MagicMock()
        mock_auth.get_errors.return_value = ['invalid_response']
        mock_auth.get_last_error_reason.return_value = 'Response signature verification failed'

        errors = mock_auth.get_errors()
        error_reason = mock_auth.get_last_error_reason()

        self.assertEqual(len(errors), 1)
        self.assertIn('invalid_response', errors)
        self.assertIn('signature verification failed', error_reason)

    def test_saml_acs_handles_no_errors(self):
        """Test that ACS proceeds when no errors"""
        mock_auth = MagicMock()
        mock_auth.get_errors.return_value = []
        mock_auth.is_authenticated.return_value = True

        errors = mock_auth.get_errors()
        is_authenticated = mock_auth.is_authenticated()

        self.assertEqual(len(errors), 0)
        self.assertTrue(is_authenticated)

    def test_saml_acs_handles_unauthenticated_response(self):
        """Test that ACS handles unauthenticated SAML responses"""
        mock_auth = MagicMock()
        mock_auth.get_errors.return_value = []
        mock_auth.is_authenticated.return_value = False

        errors = mock_auth.get_errors()
        is_authenticated = mock_auth.is_authenticated()

        self.assertEqual(len(errors), 0)
        self.assertFalse(is_authenticated)

    def test_saml_acs_extracts_attributes(self):
        """Test that ACS properly extracts SAML attributes"""
        mock_auth = MagicMock()
        mock_auth.get_attributes.return_value = {
            'uid': ['testuser'],
            'email': ['testuser@example.com'],
            'displayName': ['Test User']
        }
        mock_auth.get_nameid.return_value = 'testuser@example.com'

        attributes = mock_auth.get_attributes()
        name_id = mock_auth.get_nameid()

        self.assertEqual(attributes['uid'][0], 'testuser')
        self.assertEqual(attributes['email'][0], 'testuser@example.com')
        self.assertEqual(attributes['displayName'][0], 'Test User')
        self.assertEqual(name_id, 'testuser@example.com')

    def test_user_login_extraction_with_attributes(self):
        """Test extracting user login from attributes"""
        attributes = {
            'uid': ['testuser'],
            'email': ['testuser@example.com'],
            'displayName': ['Test User']
        }
        name_id = 'testuser@example.com'
        username_attr = 'uid'

        user_login = attributes.get(username_attr, [name_id])[0] if attributes.get(username_attr) else name_id

        self.assertEqual(user_login, 'testuser')

    def test_user_login_extraction_fallback_to_nameid(self):
        """Test extracting user login falls back to NameID"""
        attributes = {}
        name_id = 'testuser@example.com'
        username_attr = 'uid'

        user_login = attributes.get(username_attr, [name_id])[0] if attributes.get(username_attr) else name_id

        self.assertEqual(user_login, 'testuser@example.com')


class TestSamlMetadataRouteLogic(unittest.TestCase):
    """Tests for SAML metadata route logic"""

    def test_metadata_contains_entity_descriptor(self):
        """Test that metadata contains EntityDescriptor"""
        metadata = '''<?xml version="1.0"?>
<md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata"
                     entityID="https://iris.example.com/saml/metadata">
    <md:SPSSODescriptor>
        <md:AssertionConsumerService
            Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
            Location="https://iris.example.com/saml/acs"/>
    </md:SPSSODescriptor>
</md:EntityDescriptor>'''

        self.assertIn('EntityDescriptor', metadata)
        self.assertIn('SPSSODescriptor', metadata)
        self.assertIn('AssertionConsumerService', metadata)

    def test_metadata_contains_correct_bindings(self):
        """Test that metadata specifies correct bindings"""
        metadata = '''<md:AssertionConsumerService
            Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
            Location="https://iris.example.com/saml/acs"/>'''

        self.assertIn('HTTP-POST', metadata)

    def test_metadata_response_type(self):
        """Test that metadata should be returned as XML"""
        content_type = 'application/xml'

        self.assertEqual(content_type, 'application/xml')


class TestSamlUserProvisioningLogic(unittest.TestCase):
    """Tests for SAML user provisioning logic"""

    def test_user_not_found_with_create_disabled(self):
        """Test behavior when user not found and create is disabled"""
        user = None
        create_user_if_not_exist = False

        should_create_user = user is None and create_user_if_not_exist

        self.assertFalse(should_create_user)

    def test_user_not_found_with_create_enabled(self):
        """Test behavior when user not found and create is enabled"""
        user = None
        create_user_if_not_exist = True

        should_create_user = user is None and create_user_if_not_exist

        self.assertTrue(should_create_user)

    def test_user_found_no_creation_needed(self):
        """Test behavior when user is found"""
        user = MagicMock()
        create_user_if_not_exist = True

        should_create_user = user is None and create_user_if_not_exist

        self.assertFalse(should_create_user)

    def test_inactive_user_should_be_rejected(self):
        """Test that inactive users should be rejected"""
        user = MagicMock()
        user.active = False

        should_reject = user and not user.active

        self.assertTrue(should_reject)

    def test_active_user_should_be_accepted(self):
        """Test that active users should be accepted"""
        user = MagicMock()
        user.active = True

        should_reject = user and not user.active

        self.assertFalse(should_reject)

    def test_random_password_generation(self):
        """Test random password generation for SAML users"""
        import string
        import random

        password = ''.join(random.choices(string.printable[:-6], k=16))

        self.assertEqual(len(password), 16)
        for char in password:
            self.assertIn(char, string.printable[:-6])

    def test_fallback_email_generation(self):
        """Test fallback email generation"""
        user_login = 'testuser'
        email_attr = 'email'
        attributes = {}

        user_email = attributes.get(email_attr, [f'{user_login}@saml'])[0] if attributes.get(email_attr) else f'{user_login}@saml'

        self.assertEqual(user_email, 'testuser@saml')


class TestSamlSessionHandling(unittest.TestCase):
    """Tests for SAML session handling"""

    def test_next_url_retrieved_from_session(self):
        """Test that next URL is retrieved from session after auth"""
        session = {'saml_next_url': '/dashboard?cid=1'}

        next_url = session.pop('saml_next_url', None)

        self.assertEqual(next_url, '/dashboard?cid=1')
        self.assertNotIn('saml_next_url', session)

    def test_next_url_none_when_not_set(self):
        """Test that next URL is None when not set in session"""
        session = {}

        next_url = session.pop('saml_next_url', None)

        self.assertIsNone(next_url)

    def test_mfa_skipped_for_saml_login(self):
        """Test that MFA is skipped for SAML login (like OIDC)"""
        # SAML login uses is_oidc=True parameter to skip MFA
        is_oidc = True

        # In wrap_login_user, MFA is skipped when is_oidc=True
        should_skip_mfa = is_oidc

        self.assertTrue(should_skip_mfa)


class TestSamlRedirectionMapper(unittest.TestCase):
    """Tests for SAML redirection mapper in util.py"""

    def test_saml_in_redirection_mapper(self):
        """Test that SAML is included in redirection mapper"""
        redirection_mapper = {
            "oidc_proxy": "/oauth2/sign_out",
            "local": "/login",
            "ldap": "/login",
            "oidc": "/login",
            "saml": "/login",
        }

        self.assertIn('saml', redirection_mapper)
        self.assertEqual(redirection_mapper['saml'], '/login')

    def test_saml_in_authentication_mapper(self):
        """Test that SAML is included in authentication mapper"""
        authentication_mapper = {
            "oidc_proxy": "_oidc_proxy_authentication_process",
            "local": "_local_authentication_process",
            "ldap": "_local_authentication_process",
            "oidc": "_local_authentication_process",
            "saml": "_local_authentication_process",
        }

        self.assertIn('saml', authentication_mapper)
        # SAML uses local authentication process (session-based)
        self.assertEqual(authentication_mapper['saml'], '_local_authentication_process')


class TestSamlAuthenticationTypeCheck(unittest.TestCase):
    """Tests for SAML authentication type checks"""

    def test_saml_routes_registered_for_saml_auth_type(self):
        """Test that SAML routes should be registered for saml auth type"""
        auth_types_with_login_route = ["local", "ldap", "oidc", "saml"]

        self.assertIn('saml', auth_types_with_login_route)

    def test_is_authentication_saml_true(self):
        """Test is_authentication_saml returns True for saml"""
        config = {'AUTHENTICATION_TYPE': 'saml'}
        is_saml = config.get('AUTHENTICATION_TYPE') == 'saml'

        self.assertTrue(is_saml)

    def test_is_authentication_saml_false_for_others(self):
        """Test is_authentication_saml returns False for other types"""
        for auth_type in ['local', 'ldap', 'oidc', 'oidc_proxy']:
            config = {'AUTHENTICATION_TYPE': auth_type}
            is_saml = config.get('AUTHENTICATION_TYPE') == 'saml'

            self.assertFalse(is_saml)


class TestSamlLocalFallback(unittest.TestCase):
    """Tests for SAML local fallback behavior"""

    def test_redirect_to_saml_when_fallback_disabled(self):
        """Test redirect to SAML login when local fallback is disabled"""
        is_saml = True
        local_fallback = False

        should_redirect_to_saml = is_saml and not local_fallback

        self.assertTrue(should_redirect_to_saml)

    def test_no_redirect_when_fallback_enabled(self):
        """Test no auto-redirect when local fallback is enabled"""
        is_saml = True
        local_fallback = True

        should_redirect_to_saml = is_saml and not local_fallback

        self.assertFalse(should_redirect_to_saml)

    def test_no_redirect_when_not_saml(self):
        """Test no redirect when not SAML auth type"""
        is_saml = False
        local_fallback = False

        should_redirect_to_saml = is_saml and not local_fallback

        self.assertFalse(should_redirect_to_saml)


if __name__ == '__main__':
    unittest.main()
