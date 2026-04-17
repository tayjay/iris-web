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

from flask import Blueprint

from app.models.iocs import Pap
from app.blueprints.access_controls import ac_api_requires
from app.blueprints.responses import response_error
from app.blueprints.responses import response_success

manage_pap_type_rest_blueprint = Blueprint('manage_pap_types_rest', __name__)


@manage_pap_type_rest_blueprint.route('/manage/pap/list', methods=['GET'])
@ac_api_requires()
def list_pap_types():
    lstatus = Pap.query.all()

    return response_success("", data=lstatus)


@manage_pap_type_rest_blueprint.route('/manage/pap/<int:cur_id>', methods=['GET'])
@ac_api_requires()
def get_pap_type(cur_id):

    pap_type = Pap.query.filter(Pap.pap_id == cur_id).first()
    if not pap_type:
        return response_error(f"Invalid PAP ID {cur_id}")

    return response_success("", data=pap_type)
