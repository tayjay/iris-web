#  IRIS Source Code
#  Copyright (C) 2024 - DFIR-IRIS
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

from datetime import datetime

import csv
import logging as log
import marshmallow
from flask import Blueprint
from flask import request
from marshmallow import ValidationError

from app.db import db
from app.blueprints.rest.case_comments import case_comment_update
from app.blueprints.rest.endpoints import endpoint_deprecated
from app.blueprints.iris_user import iris_current_user
from app.business.iocs import iocs_create
from app.business.iocs import iocs_update
from app.business.iocs import iocs_delete
from app.business.iocs import iocs_get
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.datamgmt.case.case_iocs_db import add_comment_to_ioc
from app.datamgmt.case.case_iocs_db import delete_ioc_comment
from app.datamgmt.case.case_iocs_db import get_case_ioc_comment
from app.datamgmt.case.case_iocs_db import get_case_ioc_comments
from app.datamgmt.case.case_iocs_db import get_detailed_iocs
from app.datamgmt.case.case_iocs_db import get_ioc_links
from app.datamgmt.case.case_iocs_db import get_ioc_type_id
from app.datamgmt.case.case_iocs_db import get_tlps_dict
from app.datamgmt.case.case_iocs_db import get_paps_dict
from app.datamgmt.manage.manage_attribute_db import get_default_custom_attributes
from app.datamgmt.states import get_ioc_state
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.models.authorization import CaseAccessLevel
from app.models.iocs import Ioc
from app.schema.marshables import CommentSchema
from app.schema.marshables import IocSchema
from app.blueprints.access_controls import ac_requires_case_identifier
from app.blueprints.access_controls import ac_fast_check_current_user_has_case_access
from app.blueprints.access_controls import ac_api_requires
from app.blueprints.access_controls import ac_api_return_access_denied
from app.blueprints.responses import response_error
from app.blueprints.responses import response_success
from app.iris_engine.module_handler.module_handler import call_deprecated_on_preload_modules_hook
from app.iris_engine.access_control.utils import ac_get_fast_user_cases_access

case_ioc_rest_blueprint = Blueprint('case_ioc_rest', __name__)

_DUPLICATE_MODE_SKIP = 'skip'
_DUPLICATE_MODE_MERGE = 'merge'
_SUPPORTED_DUPLICATE_MODES = {_DUPLICATE_MODE_SKIP, _DUPLICATE_MODE_MERGE}


def _merge_csv_text(existing_text, incoming_text):
    existing = (existing_text or '').strip()
    incoming = (incoming_text or '').strip()
    if not incoming:
        return existing_text, False
    if not existing:
        return incoming, True
    if existing == incoming:
        return existing_text, False
    return f'{existing}\n\n{incoming}', True


def _merge_csv_tags(existing_tags, incoming_tags):
    existing_items = [item.strip() for item in (existing_tags or '').split(',') if item and item.strip()]
    incoming_items = [item.strip() for item in (incoming_tags or '').split(',') if item and item.strip()]
    if not incoming_items:
        return existing_tags, False

    merged = list(existing_items)
    seen = set(existing_items)
    for tag in incoming_items:
        if tag not in seen:
            merged.append(tag)
            seen.add(tag)

    new_value = ','.join(merged)
    return new_value, new_value != (existing_tags or '')


def _get_existing_ioc(caseid, ioc_value, ioc_type_id):
    return Ioc.query.filter(
        Ioc.case_id == caseid,
        Ioc.ioc_value == ioc_value,
        Ioc.ioc_type_id == ioc_type_id
    ).first()


def _parse_ioc_csv(caseid, jsdata, duplicate_mode):
    headers = 'ioc_value,ioc_type,ioc_description,ioc_tags,ioc_tlp,ioc_pap'
    csv_lines = jsdata['CSVData'].splitlines()  # unavoidable since the file is passed as a string
    if not csv_lines:
        return {
            'errors': ['Empty CSV file'],
            'rows': [],
            'total_rows': 0,
            'duplicate_rows_in_file': 0
        }

    first_line = csv_lines[0].lower().strip()
    if first_line != headers:
        if first_line == 'ioc_value,ioc_type,ioc_description,ioc_tags,ioc_tlp':
            headers = 'ioc_value,ioc_type,ioc_description,ioc_tags,ioc_tlp'
        else:
            csv_lines.insert(0, headers)

    csv_data = csv.DictReader(csv_lines, quotechar='"', delimiter=',')
    tlp_dict = get_tlps_dict()
    pap_dict = get_paps_dict()

    errors = []
    total_rows = 0
    duplicate_rows_in_file = 0
    prepared_rows = []
    dedupe_index = {}

    for index, row in enumerate(csv_data):
        total_rows += 1
        missing_field = False
        for header in headers.split(','):
            if row.get(header) is None:
                errors.append(f'{header} is missing for row {index}')
                missing_field = True

        if missing_field:
            continue

        row['ioc_value'] = (row.get('ioc_value') or '').strip()
        row['ioc_type'] = (row.get('ioc_type') or '').strip()
        row['ioc_description'] = row.get('ioc_description') or ''
        row['ioc_tags'] = (row.get('ioc_tags') or '').replace('|', ',').strip()

        if not row.get('ioc_value'):
            errors.append(f'Empty IOC value for row {index}')
            track_activity('Attempted to upload an empty IOC value')
            continue

        if row.get('ioc_tlp') in tlp_dict:
            row['ioc_tlp_id'] = tlp_dict[row.get('ioc_tlp')]
        else:
            row['ioc_tlp_id'] = ''
        row.pop('ioc_tlp', None)

        if row.get('ioc_pap') is not None:
            if row.get('ioc_pap') in pap_dict:
                row['ioc_pap_id'] = pap_dict[row.get('ioc_pap')]
            else:
                row['ioc_pap_id'] = ''
            row.pop('ioc_pap', None)

        type_id = get_ioc_type_id(row['ioc_type'].lower()) if row.get('ioc_type') else None
        if not type_id:
            ioc_value = row.get('ioc_value')
            ioc_type = row.get('ioc_type')
            errors.append(f'{ioc_value} (invalid ioc type: {ioc_type}) for row {index}')
            log.error(f'Unrecognised IOC type {ioc_type}')
            continue

        row['ioc_type_id'] = type_id.type_id
        row.pop('ioc_type', None)

        dedupe_key = (row['ioc_value'], row['ioc_type_id'])
        if dedupe_key in dedupe_index:
            duplicate_rows_in_file += 1
            if duplicate_mode == _DUPLICATE_MODE_MERGE:
                existing_row = prepared_rows[dedupe_index[dedupe_key]]
                merged_tags, _ = _merge_csv_tags(existing_row.get('ioc_tags'), row.get('ioc_tags'))
                merged_desc, _ = _merge_csv_text(existing_row.get('ioc_description'), row.get('ioc_description'))
                existing_row['ioc_tags'] = merged_tags
                existing_row['ioc_description'] = merged_desc
            continue

        dedupe_index[dedupe_key] = len(prepared_rows)
        prepared_rows.append(row)

    return {
        'errors': errors,
        'rows': prepared_rows,
        'total_rows': total_rows,
        'duplicate_rows_in_file': duplicate_rows_in_file
    }


def _merge_existing_ioc(existing_ioc, incoming_row):
    updated = False

    merged_tags, changed_tags = _merge_csv_tags(existing_ioc.ioc_tags, incoming_row.get('ioc_tags'))
    if changed_tags:
        existing_ioc.ioc_tags = merged_tags
        updated = True

    merged_desc, changed_desc = _merge_csv_text(existing_ioc.ioc_description, incoming_row.get('ioc_description'))
    if changed_desc:
        existing_ioc.ioc_description = merged_desc
        updated = True

    if updated:
        db.session.commit()

    return updated


@case_ioc_rest_blueprint.route('/case/ioc/list', methods=['GET'])
@endpoint_deprecated('GET', '/api/v2/cases/<int:identifier>/iocs')
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def case_list_ioc(caseid):
    iocs = get_detailed_iocs(caseid)

    ret = {'ioc': []}

    for ioc in iocs:
        out = ioc._asdict()

        # Get links of the IoCs seen in other cases
        user_search_limitations = ac_get_fast_user_cases_access(iris_current_user.id)
        ial = get_ioc_links(ioc.ioc_id, user_search_limitations)

        out['link'] = [row._asdict() for row in ial]
        # Legacy, must be changed next version
        out['misp_link'] = None

        ret['ioc'].append(out)

    ret['state'] = get_ioc_state(caseid=caseid)

    return response_success('', data=ret)


@case_ioc_rest_blueprint.route('/case/ioc/state', methods=['GET'])
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def case_ioc_state(caseid):
    os = get_ioc_state(caseid=caseid)
    if os:
        return response_success(data=os)
    return response_error('No IOC state for this case.')


@case_ioc_rest_blueprint.route('/case/ioc/add', methods=['POST'])
@endpoint_deprecated('POST', '/api/v2/cases/<int:identifier>/iocs')
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def deprecated_case_add_ioc(caseid):
    ioc_schema = IocSchema()

    try:
        request_data = call_deprecated_on_preload_modules_hook('ioc_create', request.get_json(), caseid)
        request_data['case_id'] = caseid
        ioc = ioc_schema.load(request_data)
        ioc = iocs_create(ioc)
        return response_success('IOC added', data=ioc_schema.dump(ioc))
    except ValidationError as e:
        return response_error('Data error', e.messages)
    except BusinessProcessingError as e:
        return response_error(e.get_message(), data=e.get_data())


@case_ioc_rest_blueprint.route('/case/ioc/upload', methods=['POST'])
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_upload_ioc(caseid):
    try:
        add_ioc_schema = IocSchema()
        jsdata = request.get_json()

        csv_options = jsdata.get('CSVOptions') if jsdata.get('CSVOptions') else {}
        duplicate_mode = csv_options.get('duplicate_mode', _DUPLICATE_MODE_SKIP)
        if duplicate_mode not in _SUPPORTED_DUPLICATE_MODES:
            return response_error(msg='Data error', data={'duplicate_mode': 'Unsupported duplicate handling mode'})

        parse_data = _parse_ioc_csv(caseid, jsdata, duplicate_mode)
        ret = []
        errors = list(parse_data['errors'])
        created = 0
        merged = 0
        skipped_existing = 0

        for row in parse_data['rows']:
            existing_ioc = _get_existing_ioc(caseid, row['ioc_value'], row['ioc_type_id'])
            if existing_ioc:
                if duplicate_mode == _DUPLICATE_MODE_MERGE:
                    if _merge_existing_ioc(existing_ioc, row):
                        merged += 1
                        track_activity(f'merged ioc "{existing_ioc.ioc_value}" from CSV import', caseid=caseid)
                else:
                    skipped_existing += 1
                continue

            try:
                request_data = call_modules_hook('on_preload_ioc_create', row, caseid=caseid)
                request_data['case_id'] = caseid

                ioc = add_ioc_schema.load(request_data)
                ioc.custom_attributes = get_default_custom_attributes('ioc')
                ioc = iocs_create(ioc)
                ret.append(request_data)
                created += 1
            except marshmallow.exceptions.ValidationError as e:
                errors.append(f'Data error for IOC {row.get("ioc_value")}: {e.messages}')
            except BusinessProcessingError as e:
                errors.append(e.get_message())

        if len(errors) == 0:
            msg = 'Successfully imported data.'
        else:
            msg = 'Data is imported but we got errors with the following rows:\n- ' + '\n- '.join(errors)

        summary = {
            'total_rows': parse_data['total_rows'],
            'duplicate_rows_in_file': parse_data['duplicate_rows_in_file'],
            'created_rows': created,
            'merged_rows': merged,
            'skipped_existing_rows': skipped_existing,
            'invalid_rows': len(errors)
        }

        return response_success(msg=msg, data={'created': ret, 'summary': summary})

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg='Data error', data=e.messages)


@case_ioc_rest_blueprint.route('/case/ioc/upload/preview', methods=['POST'])
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_upload_ioc_preview(caseid):
    jsdata = request.get_json()
    csv_options = jsdata.get('CSVOptions') if jsdata.get('CSVOptions') else {}
    duplicate_mode = csv_options.get('duplicate_mode', _DUPLICATE_MODE_SKIP)
    if duplicate_mode not in _SUPPORTED_DUPLICATE_MODES:
        return response_error(msg='Data error', data={'duplicate_mode': 'Unsupported duplicate handling mode'})

    parse_data = _parse_ioc_csv(caseid, jsdata, duplicate_mode)
    duplicate_rows_in_case = 0
    for row in parse_data['rows']:
        if _get_existing_ioc(caseid, row['ioc_value'], row['ioc_type_id']):
            duplicate_rows_in_case += 1

    rows_to_create = len(parse_data['rows']) - duplicate_rows_in_case
    rows_to_merge = duplicate_rows_in_case if duplicate_mode == _DUPLICATE_MODE_MERGE else 0

    return response_success(
        msg='CSV preview ready',
        data={
            'duplicate_mode': duplicate_mode,
            'total_rows': parse_data['total_rows'],
            'valid_rows': len(parse_data['rows']),
            'invalid_rows': len(parse_data['errors']),
            'duplicate_rows_in_file': parse_data['duplicate_rows_in_file'],
            'duplicate_rows_in_case': duplicate_rows_in_case,
            'rows_to_create': rows_to_create,
            'rows_to_merge': rows_to_merge,
            'errors': parse_data['errors']
        }
    )


@case_ioc_rest_blueprint.route('/case/ioc/delete/<int:cur_id>', methods=['POST'])
@endpoint_deprecated('DELETE', '/api/v2/cases/<int:case_identifier>/iocs/<int:cur_id>')
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def deprecated_case_delete_ioc(cur_id: int, caseid: int):
    try:
        ioc = iocs_get(cur_id)
        if not ac_fast_check_current_user_has_case_access(ioc.case_id, [CaseAccessLevel.full_access]):
            return ac_api_return_access_denied(caseid=ioc.case_id)

        msg = iocs_delete(ioc)
        return response_success(msg=msg)

    except ObjectNotFoundError:
        return response_error('Not a valid IOC for this case')

    except BusinessProcessingError as e:
        return response_error(e.get_message())


@case_ioc_rest_blueprint.route('/case/ioc/<int:cur_id>', methods=['GET'])
@endpoint_deprecated('GET', '/api/v2/cases/<int:case_identifier>/iocs/<int:cur_id>')
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def deprecated_case_view_ioc(cur_id, caseid):
    ioc_schema = IocSchema()
    try:
        ioc = iocs_get(cur_id)

        return response_success(data=ioc_schema.dump(ioc))
    except ObjectNotFoundError:
        return response_error('Invalid IOC identifier')


@case_ioc_rest_blueprint.route('/case/ioc/update/<int:cur_id>', methods=['POST'])
@endpoint_deprecated('POST', '/api/v2/cases/<int:case_identifier>/iocs/<int:cur_id>')
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_update_ioc(cur_id, caseid):
    ioc_schema = IocSchema()

    try:
        ioc = iocs_get(cur_id)

        request_data = call_deprecated_on_preload_modules_hook('ioc_update', request.get_json(), ioc.case_id)

        # validate before saving
        request_data['ioc_id'] = ioc.ioc_id
        request_data['case_id'] = ioc.case_id
        ioc_sc = ioc_schema.load(request_data, instance=ioc, partial=True)
        ioc = iocs_update(ioc, ioc_sc)
        return response_success(f'Updated ioc "{ioc.ioc_value}"', data=ioc_schema.dump(ioc))

    except ValidationError as e:
        return response_error('Data error', e.messages)

    except BusinessProcessingError as e:
        return response_error(e.get_message(), data=e.get_data())


@case_ioc_rest_blueprint.route('/case/ioc/<int:cur_id>/comments/list', methods=['GET'])
@endpoint_deprecated('GET', '/api/v2/iocs/{ioc_identifier}/comments')
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def case_comment_ioc_list(cur_id, caseid):
    ioc_comments = get_case_ioc_comments(cur_id)
    if ioc_comments is None:
        return response_error('Invalid ioc ID')

    return response_success(data=CommentSchema(many=True).dump(ioc_comments))


@case_ioc_rest_blueprint.route('/case/ioc/<int:cur_id>/comments/add', methods=['POST'])
@endpoint_deprecated('POST', '/api/v2/iocs/{ioc_identifier}/comments')
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_comment_ioc_add(cur_id, caseid):
    try:
        ioc = iocs_get(cur_id)

        comment_schema = CommentSchema()

        comment = comment_schema.load(request.get_json())
        comment.comment_case_id = ioc.case_id
        comment.comment_user_id = iris_current_user.id
        comment.comment_date = datetime.now()
        comment.comment_update_date = datetime.now()
        db.session.add(comment)
        db.session.commit()

        add_comment_to_ioc(ioc.ioc_id, comment.comment_id)

        db.session.commit()

        hook_data = {
            'comment': comment_schema.dump(comment),
            'ioc': IocSchema().dump(ioc)
        }
        call_modules_hook('on_postload_ioc_commented', hook_data, caseid=ioc.case_id)

        track_activity(f'ioc "{ioc.ioc_value}" commented', caseid=ioc.case_id)
        return response_success('IOC commented', data=comment_schema.dump(comment))

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg='Data error', data=e.normalized_messages())
    except ObjectNotFoundError:
        return response_error('Invalid ioc ID')


@case_ioc_rest_blueprint.route('/case/ioc/<int:cur_id>/comments/<int:com_id>', methods=['GET'])
@endpoint_deprecated('GET', '/api/v2/iocs/{ioc_identifier}/comments/{identifier}')
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def case_comment_ioc_get(cur_id, com_id, caseid):
    comment = get_case_ioc_comment(cur_id, com_id)
    if not comment:
        return response_error('Invalid comment ID')

    return response_success(data=comment._asdict())


@case_ioc_rest_blueprint.route('/case/ioc/<int:cur_id>/comments/<int:com_id>/edit', methods=['POST'])
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_comment_ioc_edit(cur_id, com_id, caseid):
    return case_comment_update(com_id, 'ioc', caseid)


@case_ioc_rest_blueprint.route('/case/ioc/<int:cur_id>/comments/<int:com_id>/delete', methods=['POST'])
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_comment_ioc_delete(cur_id, com_id, caseid):
    success, msg = delete_ioc_comment(iris_current_user.id, cur_id, com_id)
    if not success:
        return response_error(msg)

    call_modules_hook('on_postload_ioc_comment_delete', com_id, caseid=caseid)

    track_activity(f'comment {com_id} on ioc {cur_id} deleted', caseid=caseid)
    return response_success(msg)
