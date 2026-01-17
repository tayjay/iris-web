#  IRIS Source Code
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

from onelogin.saml2.auth import OneLogin_Saml2_Auth
from onelogin.saml2.settings import OneLogin_Saml2_Settings


def prepare_flask_request(request):
    """
    Convert Flask request to python3-saml format

    Args:
        request: Flask request object

    Returns:
        dict: Request data formatted for python3-saml
    """
    url_data = request.url.split('?')
    return {
        'https': 'on' if request.scheme == 'https' else 'off',
        'http_host': request.host,
        'server_port': request.environ.get('SERVER_PORT', '443' if request.scheme == 'https' else '80'),
        'script_name': request.path,
        'get_data': request.args.copy(),
        'post_data': request.form.copy(),
        'query_string': request.query_string.decode('utf-8')
    }


def get_saml_settings(app) -> dict:
    """
    Build python3-saml settings dict from app config

    Args:
        app: Flask application with SAML configuration

    Returns:
        dict: Settings dictionary for python3-saml
    """
    # Build IdP settings
    idp_settings = {
        'entityId': app.config.get('SAML_IDP_ENTITY_ID'),
        'singleSignOnService': {
            'url': app.config.get('SAML_IDP_SSO_URL'),
            'binding': 'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect'
        },
        'x509cert': app.config.get('SAML_IDP_X509_CERT', '')
    }

    # Add SLO URL if configured
    slo_url = app.config.get('SAML_IDP_SLO_URL')
    if slo_url:
        idp_settings['singleLogoutService'] = {
            'url': slo_url,
            'binding': 'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect'
        }

    # Build SP settings
    sp_settings = {
        'entityId': app.config.get('SAML_SP_ENTITY_ID'),
        'assertionConsumerService': {
            'url': app.config.get('SAML_SP_ACS_URL'),
            'binding': 'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST'
        },
        'NameIDFormat': 'urn:oasis:names:tc:SAML:1.1:nameid-format:unspecified'
    }

    # Add SP certificate and key if configured (for signing)
    sp_cert = app.config.get('SAML_SP_X509_CERT')
    sp_key = app.config.get('SAML_SP_PRIVATE_KEY')
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
        'wantMessagesSigned': app.config.get('SAML_WANT_RESPONSE_SIGNED', True),
        'wantAssertionsSigned': app.config.get('SAML_WANT_ASSERTIONS_SIGNED', True),
        'wantNameId': True,
        'wantNameIdEncrypted': False,
        'wantAssertionsEncrypted': False,
        'allowSingleLabelDomains': False,
        'signatureAlgorithm': 'http://www.w3.org/2001/04/xmldsig-more#rsa-sha256',
        'digestAlgorithm': 'http://www.w3.org/2001/04/xmlenc#sha256'
    }

    settings = {
        'strict': True,
        'debug': app.config.get('DEVELOPMENT', False),
        'sp': sp_settings,
        'idp': idp_settings,
        'security': security_settings
    }

    return settings


def get_saml_auth(request, app) -> OneLogin_Saml2_Auth:
    """
    Create SAML Auth object for request

    Args:
        request: Flask request object
        app: Flask application

    Returns:
        OneLogin_Saml2_Auth: SAML auth object ready to process requests
    """
    req = prepare_flask_request(request)
    saml_settings = get_saml_settings(app)
    return OneLogin_Saml2_Auth(req, saml_settings)


def get_saml_metadata(app) -> str:
    """
    Generate SP metadata XML for IdP configuration

    Args:
        app: Flask application with SAML configuration

    Returns:
        str: SP metadata XML string
    """
    saml_settings = get_saml_settings(app)
    settings = OneLogin_Saml2_Settings(saml_settings, sp_validation_only=True)
    metadata = settings.get_sp_metadata()
    errors = settings.validate_metadata(metadata)

    if errors:
        raise Exception(f"Invalid SP metadata: {', '.join(errors)}")

    return metadata
