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

import csv
from datetime import datetime
from sqlalchemy import func
from flask import Blueprint
from flask import request
from marshmallow import ValidationError

from app.db import db
from app.blueprints.rest.case_comments import case_comment_update
from app.blueprints.rest.endpoints import endpoint_deprecated
from app.business.assets import assets_delete
from app.business.assets import assets_create
from app.business.assets import assets_get
from app.business.assets import assets_update
from app.blueprints.iris_user import iris_current_user
from app.models.errors import BusinessProcessingError
from app.datamgmt.case.case_assets_db import get_raw_assets
from app.datamgmt.case.case_assets_db import get_linked_iocs_finfo_from_asset
from app.datamgmt.case.case_assets_db import add_comment_to_asset
from app.datamgmt.case.case_assets_db import create_asset
from app.datamgmt.case.case_assets_db import delete_asset_comment
from app.datamgmt.case.case_assets_db import get_asset
from app.datamgmt.case.assets_type import get_asset_type_by_name_case_insensitive
from app.datamgmt.case.case_assets_db import get_assets
from app.datamgmt.case.case_assets_db import get_assets_ioc_links
from app.datamgmt.case.case_assets_db import get_case_asset_comment
from app.datamgmt.case.case_assets_db import get_case_asset_comments
from app.datamgmt.case.case_assets_db import get_similar_assets
from app.datamgmt.case.case_db import get_case_client_id
from app.datamgmt.comments import get_comment
from app.datamgmt.manage.manage_attribute_db import get_default_custom_attributes
from app.datamgmt.manage.manage_users_db import get_user_cases_fast
from app.datamgmt.states import get_assets_state
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.models.assets import AnalysisStatus
from app.models.assets import CaseAssets
from app.models.authorization import CaseAccessLevel
from app.schema.marshables import CaseAssetsSchema
from app.schema.marshables import CommentSchema
from app.blueprints.access_controls import ac_requires_case_identifier, ac_fast_check_current_user_has_case_access
from app.blueprints.access_controls import ac_api_requires
from app.blueprints.responses import response_error
from app.blueprints.responses import response_success
from app.blueprints.access_controls import ac_api_return_access_denied

case_assets_rest_blueprint = Blueprint('case_assets_rest', __name__)

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


def _normalize_asset_csv_row(row):
    normalized = dict(row)
    normalized['asset_name'] = (normalized.get('asset_name') or '').strip()
    normalized['asset_type_name'] = (normalized.get('asset_type_name') or '').strip()
    normalized['asset_description'] = normalized.get('asset_description') or ''
    normalized['asset_ip'] = (normalized.get('asset_ip') or '').strip()
    normalized['asset_domain'] = (normalized.get('asset_domain') or '').strip()
    normalized['asset_tags'] = ((normalized.get('asset_tags') or '').replace('|', ',')).strip()
    return normalized


def _get_existing_asset(caseid, asset_name, asset_type_id):
    return CaseAssets.query.filter(
        CaseAssets.case_id == caseid,
        CaseAssets.asset_type_id == asset_type_id,
        func.lower(CaseAssets.asset_name) == func.lower(asset_name)
    ).first()


def _parse_asset_csv(caseid, jsdata, duplicate_mode):
    headers = 'asset_name,asset_type_name,asset_description,asset_ip,asset_domain,asset_tags'
    csv_lines = jsdata['CSVData'].splitlines()  # unavoidable since the file is passed as a string
    if not csv_lines:
        return {
            'errors': ['Empty CSV file'],
            'rows': [],
            'total_rows': 0,
            'duplicate_rows_in_file': 0
        }

    if csv_lines[0].lower() != headers:
        csv_lines.insert(0, headers)

    csv_data = csv.DictReader(csv_lines, delimiter=',')
    analysis_status = AnalysisStatus.query.filter(AnalysisStatus.name == 'Unspecified').first()
    analysis_status_id = analysis_status.id

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

        row = _normalize_asset_csv_row(row)

        if not row.get('asset_name'):
            errors.append(f'Empty asset name for row {index}')
            track_activity('Attempted to upload an empty asset name')
            continue

        if not row.get('asset_type_name'):
            errors.append(f'Empty asset type for row {index}')
            track_activity('Attempted to upload an empty asset type')
            continue

        asset_type = get_asset_type_by_name_case_insensitive(row['asset_type_name'])
        if not asset_type:
            errors.append(f"{row.get('asset_name')} (invalid asset type: {row.get('asset_type_name')}) for row {index}")
            track_activity(f"Attempted to upload unrecognized asset type \"{row.get('asset_type_name')}\"")
            continue

        row['asset_type_id'] = asset_type.asset_id
        row['analysis_status_id'] = analysis_status_id
        row.pop('asset_type_name', None)

        dedupe_key = (row['asset_name'].lower(), row['asset_type_id'])
        if dedupe_key in dedupe_index:
            duplicate_rows_in_file += 1
            if duplicate_mode == _DUPLICATE_MODE_MERGE:
                existing_row = prepared_rows[dedupe_index[dedupe_key]]
                merged_tags, _ = _merge_csv_tags(existing_row.get('asset_tags'), row.get('asset_tags'))
                merged_desc, _ = _merge_csv_text(existing_row.get('asset_description'), row.get('asset_description'))
                existing_row['asset_tags'] = merged_tags
                existing_row['asset_description'] = merged_desc
                if not existing_row.get('asset_ip') and row.get('asset_ip'):
                    existing_row['asset_ip'] = row.get('asset_ip')
                if not existing_row.get('asset_domain') and row.get('asset_domain'):
                    existing_row['asset_domain'] = row.get('asset_domain')
            continue

        dedupe_index[dedupe_key] = len(prepared_rows)
        prepared_rows.append(row)

    return {
        'errors': errors,
        'rows': prepared_rows,
        'total_rows': total_rows,
        'duplicate_rows_in_file': duplicate_rows_in_file
    }


def _merge_existing_asset(existing_asset, incoming_row):
    updated = False

    merged_tags, changed_tags = _merge_csv_tags(existing_asset.asset_tags, incoming_row.get('asset_tags'))
    if changed_tags:
        existing_asset.asset_tags = merged_tags
        updated = True

    merged_desc, changed_desc = _merge_csv_text(existing_asset.asset_description, incoming_row.get('asset_description'))
    if changed_desc:
        existing_asset.asset_description = merged_desc
        updated = True

    if not (existing_asset.asset_ip or '').strip() and (incoming_row.get('asset_ip') or '').strip():
        existing_asset.asset_ip = incoming_row.get('asset_ip').strip()
        updated = True

    if not (existing_asset.asset_domain or '').strip() and (incoming_row.get('asset_domain') or '').strip():
        existing_asset.asset_domain = incoming_row.get('asset_domain').strip()
        updated = True

    if updated:
        existing_asset.date_update = datetime.utcnow()
        db.session.commit()

    return updated


@case_assets_rest_blueprint.route('/case/assets/filter', methods=['GET'])
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_filter_assets(caseid):
    """
    Returns the list of assets from the case.
    :return: A JSON object containing the assets of the case, enhanced with assets seen on other cases.
    """

    # Get all assets objects from the case and the customer id
    ret = {}
    assets = CaseAssetsSchema().dump(get_raw_assets(caseid), many=True)
    customer_id = get_case_client_id(caseid)

    ioc_links_req = get_assets_ioc_links(caseid)

    cache_ioc_link = {}
    for ioc in ioc_links_req:

        if ioc.asset_id not in cache_ioc_link:
            cache_ioc_link[ioc.asset_id] = [ioc._asdict()]
        else:
            cache_ioc_link[ioc.asset_id].append(ioc._asdict())

    cases_access = get_user_cases_fast(iris_current_user.id)

    for a in assets:
        a['ioc_links'] = cache_ioc_link.get(a['asset_id'])

        if len(assets) < 300:
            # Find similar assets from other cases with the same customer
            a['link'] = list(get_similar_assets(
                a['asset_name'], a['asset_type_id'], caseid, customer_id, cases_access))
        else:
            a['link'] = []

    ret['assets'] = assets

    ret['state'] = get_assets_state(caseid)

    return response_success("", data=ret)


@case_assets_rest_blueprint.route('/case/assets/list', methods=['GET'])
@endpoint_deprecated('GET', '/api/v2/cases/{case_identifier}/assets')
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_list_assets(caseid):
    """
    Returns the list of assets from the case.
    :return: A JSON object containing the assets of the case, enhanced with assets seen on other cases.
    """
    # Get all assets objects from the case and the customer id
    assets = get_assets(caseid)
    customer_id = get_case_client_id(caseid)

    ret = {'assets': []}

    ioc_links_req = get_assets_ioc_links(caseid)

    cache_ioc_link = {}
    for ioc in ioc_links_req:

        if ioc.asset_id not in cache_ioc_link:
            cache_ioc_link[ioc.asset_id] = [ioc._asdict()]
        else:
            cache_ioc_link[ioc.asset_id].append(ioc._asdict())

    cases_access = get_user_cases_fast(iris_current_user.id)

    for asset in assets:
        asset = asset._asdict()

        if len(assets) < 300:
            # Find similar assets from other cases with the same customer
            asset['link'] = list(get_similar_assets(
                asset['asset_name'], asset['asset_type_id'], caseid, customer_id, cases_access))
        else:
            asset['link'] = []

        asset['ioc_links'] = cache_ioc_link.get(asset['asset_id'])

        ret['assets'].append(asset)

    ret['state'] = get_assets_state(caseid)

    return response_success("", data=ret)


@case_assets_rest_blueprint.route('/case/assets/state', methods=['GET'])
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def case_assets_state(caseid):
    os = get_assets_state(caseid)
    if os:
        return response_success(data=os)
    return response_error('No assets state for this case.')


@case_assets_rest_blueprint.route('/case/assets/add', methods=['POST'])
@endpoint_deprecated('POST', '/api/v2/cases/{case_identifier}/assets')
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def deprecated_add_asset(caseid):
    asset_schema = CaseAssetsSchema()
    try:
        request_data = call_modules_hook('on_preload_asset_create', request.get_json(), caseid=caseid)
        ioc_links = request_data.get('ioc_links')
        asset = asset_schema.load(request_data)
        created_asset = assets_create(iris_current_user, caseid, asset, ioc_links)
        return response_success('Asset added', asset_schema.dump(created_asset))
    except ValidationError as e:
        return response_error('Data error', data=e.messages)
    except BusinessProcessingError as e:
        return response_error(e.get_message(), e.get_data())


@case_assets_rest_blueprint.route('/case/assets/upload', methods=['POST'])
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_upload_asset(caseid):
    try:
        add_asset_schema = CaseAssetsSchema()
        jsdata = request.get_json()
        csv_options = jsdata.get('CSVOptions') if jsdata.get('CSVOptions') else {}
        duplicate_mode = csv_options.get('duplicate_mode', _DUPLICATE_MODE_SKIP)
        if duplicate_mode not in _SUPPORTED_DUPLICATE_MODES:
            return response_error(msg='Data error', data={'duplicate_mode': 'Unsupported duplicate handling mode'})

        parse_data = _parse_asset_csv(caseid, jsdata, duplicate_mode)
        errors = list(parse_data['errors'])
        created = 0
        merged = 0
        skipped_existing = 0
        ret = []

        for row in parse_data['rows']:
            existing_asset = _get_existing_asset(caseid, row['asset_name'], row['asset_type_id'])
            if existing_asset:
                if duplicate_mode == _DUPLICATE_MODE_MERGE:
                    if _merge_existing_asset(existing_asset, row):
                        merged += 1
                        track_activity(f'merged asset "{existing_asset.asset_name}" from CSV import', caseid=caseid)
                else:
                    skipped_existing += 1
                continue

            try:
                request_data = call_modules_hook('on_preload_asset_create', row, caseid=caseid)
                asset_sc = add_asset_schema.load(request_data)
                asset_sc.custom_attributes = get_default_custom_attributes('asset')
                asset = create_asset(asset=asset_sc, caseid=caseid, user_id=iris_current_user.id)
                asset = call_modules_hook('on_postload_asset_create', asset, caseid=caseid)

                if not asset:
                    errors.append('Unable to add asset for internal reason')
                    continue

                created += 1
                ret.append(request_data)
                track_activity(f'added asset {asset.asset_name}', caseid=caseid)
            except ValidationError as e:
                errors.append(f'Data error for asset {row.get("asset_name")}: {e.messages}')

        summary = {
            'total_rows': parse_data['total_rows'],
            'duplicate_rows_in_file': parse_data['duplicate_rows_in_file'],
            'created_rows': created,
            'merged_rows': merged,
            'skipped_existing_rows': skipped_existing,
            'invalid_rows': len(errors)
        }

        if len(errors) == 0:
            msg = 'Successfully imported data.'
        else:
            msg = 'Data is imported but we got errors with the following rows:\n- ' + '\n- '.join(errors)

        return response_success(msg=msg, data={'created': ret, 'summary': summary})

    except ValidationError as e:
        return response_error(msg='Data error', data=e.messages)


@case_assets_rest_blueprint.route('/case/assets/upload/preview', methods=['POST'])
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_upload_asset_preview(caseid):
    jsdata = request.get_json()
    csv_options = jsdata.get('CSVOptions') if jsdata.get('CSVOptions') else {}
    duplicate_mode = csv_options.get('duplicate_mode', _DUPLICATE_MODE_SKIP)
    if duplicate_mode not in _SUPPORTED_DUPLICATE_MODES:
        return response_error(msg='Data error', data={'duplicate_mode': 'Unsupported duplicate handling mode'})

    parse_data = _parse_asset_csv(caseid, jsdata, duplicate_mode)
    duplicate_rows_in_case = 0
    for row in parse_data['rows']:
        if _get_existing_asset(caseid, row['asset_name'], row['asset_type_id']):
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


@case_assets_rest_blueprint.route('/case/assets/<int:cur_id>', methods=['GET'])
@endpoint_deprecated('GET', '/api/v2/cases/{case_identifier}/assets/{identifier}')
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def deprecated_asset_view(cur_id, caseid):
    try:

        asset = assets_get(cur_id)
        # TODO this is a code smell: shouldn't have schemas in the business layer + the CaseAssetsSchema is instantiated twice
        case_assets_schema = CaseAssetsSchema()
        data = case_assets_schema.dump(asset)
        asset_iocs = get_linked_iocs_finfo_from_asset(cur_id)
        data['linked_ioc'] = [row._asdict() for row in asset_iocs]
        return response_success(msg='Asset added', data=data)

    except BusinessProcessingError as e:
        return response_error(e.get_message())


@case_assets_rest_blueprint.route('/case/assets/update/<int:cur_id>', methods=['POST'])
@endpoint_deprecated('PUT', '/api/v2/cases/{case_identifier}/assets/{identifier}')
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def asset_update(cur_id, caseid):
    try:
        asset = get_asset(cur_id)
        if not asset:
            return response_error("Invalid asset ID for this case")

        request_data = call_modules_hook('on_preload_asset_update', request.get_json(), caseid=caseid)
        request_data['asset_id'] = asset.asset_id
        schema = CaseAssetsSchema()
        updated_asset = schema.load(request_data, instance=asset, partial=True)
        result = assets_update(updated_asset)

        return response_success(f'Updated asset {result.asset_name}', schema.dump(result))

    except BusinessProcessingError as e:
        return response_error(e.get_message(), data=e.get_data())
    except ValidationError as e:
        return response_error('Data error', data=e.messages)


@case_assets_rest_blueprint.route('/case/assets/delete/<int:cur_id>', methods=['POST'])
@endpoint_deprecated('DELETE', '/api/v2/cases/{case_identifier}/assets/{identifier}')
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def deprecated_asset_delete(cur_id, caseid):
    try:
        asset = assets_get(cur_id)
        if not ac_fast_check_current_user_has_case_access(asset.case_id, [CaseAccessLevel.full_access]):
            return ac_api_return_access_denied(caseid=asset.case_id)

        assets_delete(asset)
        return response_success('Deleted')
    except BusinessProcessingError as _:
        return response_error('Invalid asset ID for this case')


@case_assets_rest_blueprint.route('/case/assets/<int:cur_id>/comments/list', methods=['GET'])
@endpoint_deprecated('GET', '/api/v2/assets/{asset_identifier}/comments')
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def case_comment_asset_list(cur_id, caseid):
    asset_comments = get_case_asset_comments(cur_id)
    if asset_comments is None:
        return response_error('Invalid asset ID')

    return response_success(data=CommentSchema(many=True).dump(asset_comments))


@case_assets_rest_blueprint.route('/case/assets/<int:cur_id>/comments/add', methods=['POST'])
@endpoint_deprecated('POST', '/api/v2/assets/{asset_identifier}/comments')
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_comment_asset_add(cur_id, caseid):
    try:
        asset = get_asset(cur_id)
        if not asset:
            return response_error('Invalid asset ID')

        comment_schema = CommentSchema()

        comment = comment_schema.load(request.get_json())
        comment.comment_case_id = caseid
        comment.comment_user_id = iris_current_user.id
        comment.comment_date = datetime.now()
        comment.comment_update_date = datetime.now()
        db.session.add(comment)
        db.session.commit()

        add_comment_to_asset(asset.asset_id, comment.comment_id)

        db.session.commit()

        hook_data = {
            "comment": comment_schema.dump(comment),
            "asset": CaseAssetsSchema().dump(asset)
        }
        call_modules_hook('on_postload_asset_commented', hook_data, caseid=caseid)

        track_activity(f"asset \"{asset.asset_name}\" commented", caseid=caseid)
        return response_success("Asset commented", data=comment_schema.dump(comment))

    except ValidationError as e:
        return response_error(msg="Data error", data=e.normalized_messages())


@case_assets_rest_blueprint.route('/case/assets/<int:cur_id>/comments/<int:com_id>', methods=['GET'])
@endpoint_deprecated('GET', '/api/v2/assets/{asset_identifier}/comments/{identifier}')
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def case_comment_asset_get(cur_id, com_id, caseid):
    comment = get_case_asset_comment(cur_id, com_id)
    if not comment:
        return response_error("Invalid comment ID")

    return response_success(data=comment._asdict())


@case_assets_rest_blueprint.route('/case/assets/<int:cur_id>/comments/<int:com_id>/edit', methods=['POST'])
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_comment_asset_edit(cur_id, com_id, caseid):
    return case_comment_update(com_id, 'assets', caseid)


@case_assets_rest_blueprint.route('/case/assets/<int:cur_id>/comments/<int:com_id>/delete', methods=['POST'])
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_comment_asset_delete(cur_id, com_id, caseid):
    comment = get_comment(iris_current_user, com_id)
    if not comment:
        return response_error('You are not allowed to delete this comment')

    delete_asset_comment(cur_id, comment)

    call_modules_hook('on_postload_asset_comment_delete', com_id, caseid=caseid)

    track_activity(f'comment {com_id} on asset {cur_id} deleted', caseid=caseid)
    return response_success('Comment deleted')
