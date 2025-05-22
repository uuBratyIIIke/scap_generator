from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, make_response
import csv
from io import TextIOWrapper
from models import db, OperationEnum, Group, Parameter
from utils import allowed_file

parameters_bp = Blueprint('parameters', __name__)

@parameters_bp.route('/')
def index():
    parameters = Parameter.query.all()
    groups = Group.query.all()
    return render_template('index.html', parameters=parameters, groups=groups)

@parameters_bp.route('/add', methods=['GET', 'POST'])
def add_parameter():
    all_groups = Group.query.order_by(Group.name).all()
    operations = list(OperationEnum)

    if request.method == 'POST':
        if 'name' in request.form:
            try:
                operation = OperationEnum(request.form["operation"])
                new_param = Parameter(
                    name=request.form['name'],
                    value=request.form['value'],
                    description=request.form.get('description', ''),
                    comment=request.form.get('comment', ''),
                    title=request.form.get('title', ''),
                    group_id=request.form.get('group_id') or None,
                    operation=operation
                )
                db.session.add(new_param)
                db.session.commit()
                flash('Параметр успешно добавлен', 'success')
                return redirect(url_for('parameters.index'))
            except ValueError:
                flash('Недопустимое значение операции', 'error')
            except Exception as e:
                db.session.rollback()
                flash(f'Ошибка при добавлении: {str(e)}', 'error')
        elif 'csv_file' in request.files:
            file = request.files['csv_file']
            if file and allowed_file(file.filename):
                try:
                    stream = TextIOWrapper(file.stream._file, 'UTF-8')
                    csv_reader = csv.DictReader(stream, delimiter=',')
                    for row in csv_reader:
                        group_id = None
                        if 'group' in row and row['group']:
                            group = Group.query.filter_by(name=row['group']).first()
                            if group:
                                group_id = group.id
                        new_param = Parameter(
                            name=row['name'],
                            value=row['value'],
                            description=row.get('description', ''),
                            group_id=group_id,
                            comment=row.get('comment',''),
                            title=row.get('title', ''),
                            operation=row.get('operation','')
                        )
                        db.session.add(new_param)
                    db.session.commit()
                    flash('Параметры успешно импортированы', 'success')
                    return redirect(url_for('parameters.index'))
                except Exception as e:
                    db.session.rollback()
                    flash(f'Ошибка при импорте CSV: {str(e)}', 'error')
    return render_template("add.html", groups=all_groups, operations=operations)

@parameters_bp.route('/change_parameter_group/<int:param_id>', methods=['POST'])
def change_parameter_group(param_id):
    group_id = request.form.get('group_id') or None
    param = Parameter.query.get_or_404(param_id)
    param.group_id = group_id
    db.session.commit()
    flash('Группа параметра обновлена', 'success')
    return redirect(request.referrer or url_for('parameters.index'))

@parameters_bp.route('/change_parameter_group_ajax', methods=['POST'])
def change_parameter_group_ajax():
    data = request.get_json()
    param_id = data.get('param_id')
    group_id = data.get('group_id') or None
    try:
        param = Parameter.query.get_or_404(param_id)
        param.group_id = group_id
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@parameters_bp.route('/download_template')
def download_template():
    csv_data = "name,value,description,group\n"
    csv_data += "timeout,30,Таймаут соединения,Network\n"
    response = make_response(csv_data)
    response.headers['Content-Disposition'] = 'attachment; filename=parameters_template.csv'
    response.headers['Content-type'] = 'text/csv'
    return response

@parameters_bp.route('/delete/<int:id>')
def delete_parameter(id):
    parameter_to_delete = Parameter.query.get_or_404(id)
    db.session.delete(parameter_to_delete)
    db.session.commit()
    return redirect(url_for('parameters.index'))

@parameters_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_parameter(id):
    parameter = Parameter.query.get_or_404(id)
    all_groups = Group.query.order_by(Group.name).all()
    operations = list(OperationEnum)
    if request.method == 'POST':
        if not request.form['name'] or not request.form['value']:
            flash('Название и значение обязательны для заполнения', 'error')
            return render_template('edit.html', parameter=parameter, groups=all_groups)
        parameter.name = request.form['name']
        parameter.value = request.form['value']
        parameter.description = request.form.get('description', '')
        parameter.group_id = request.form.get('group_id') or None
        parameter.operation = request.form.get('operation', '')
        db.session.commit()
        return redirect(url_for('parameters.index'))
    return render_template('edit.html', parameter=parameter, groups=all_groups, operations=operations)

@parameters_bp.route('/export', methods=['POST', 'GET'])
def export_to_file():
    selected_ids = request.form.getlist('selected_ids')
    parameters = db.session.query(
        Parameter,
        Group.name.label('group_name')
    ).outerjoin(
        Group, Parameter.group_id == Group.id
    ).all()
    file_content = """<?xml version="1.0" encoding="UTF-8"?>
<oval_definitions 
  xmlns="http://oval.mitre.org/XMLSchema/oval-definitions-5"
  xmlns:oval="http://oval.mitre.org/XMLSchema/oval-common-5"
  xmlns:ind="http://oval.mitre.org/XMLSchema/oval-definitions-5#independent"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="http://oval.mitre.org/XMLSchema/oval-definitions-5 
    https://oval.mitre.org/language/version5.10.1/oval-definitions-schema.xsd 
    http://oval.mitre.org/XMLSchema/oval-definitions-5#independent 
    https://oval.mitre.org/language/version5.10.1/independent/oval-ind-definitions-schema.xsd">

  <generator>
    <oval:product_name>Custom PostgreSQL Check</oval:product_name>
    <oval:schema_version>5.10.1</oval:schema_version>
    <oval:timestamp>2025-04-08T12:00:00</oval:timestamp>
  </generator>
    """
    file_content += "<definitions>\n"
    for param, group_name in parameters:
        file_content += f"""
    <definition id=\"oval:{group_name or "custom"}:def:{param.id}\" version=\"1\" class=\"compliance\">
        <metadata>
            <title>{param.comment}</title>
            <description>{param.description}</description>
        </metadata>
        <criteria>
            <criterion test_ref=\"oval:{group_name or "custom"}:tst:{param.id}\"/>
        </criteria>
    </definition>\n\n"""
    file_content += "</definitions>\n\n"
    file_content += "<tests>\n"
    for param, group_name in parameters:
        file_content += f"""
    <ind:textfilecontent54_test id=\"oval:{group_name or "custom"}:tst:{param.id}\" version=\"1\" check=\"all\"  comment=\"{param.comment}\">
      <ind:object object_ref=\"oval:{group_name or "custom"}:obj:{param.id}\" />
      <ind:state state_ref=\"oval:{group_name or "custom"}:ste:{param.id}\" />
    </ind:textfilecontent54_test>\n\n"""
    file_content += "</tests>\n\n"
    file_content += "<objects>\n"
    for param, group_name in parameters:
        file_content += f"""
    <ind:textfilecontent54_object id=\"oval:{group_name or "custom"}:obj:{param.id}\" version=\"1\">
        <ind:filepath>/mnt/d/Studying/Pg_conf_file/pg_conf_file_04/postgresql.conf</ind:filepath>
        <ind:pattern operation=\"pattern match\">^{param.name}\s*=\s*'?(\w+)'?</ind:pattern>
        <ind:instance datatype=\"int\" operation=\"greater than or equal\">1</ind:instance>
    </ind:textfilecontent54_object>\n\n"""
    file_content += "</objects>\n\n"
    file_content += "<states>\n"
    for param, group_name in parameters:
        file_content += f"""
    <ind:textfilecontent54_state id=\"oval:{group_name or "custom"}:ste:{param.id}\" version=\"1\">
        <ind:text operation=\"{param.operation}\">^{param.name}\s*=\s*'?({param.value})'?</ind:text>
    </ind:textfilecontent54_state>\n\n"""
    file_content += "</states> </oval_definitions>"
    response = make_response(file_content)
    response.headers['Content-Disposition'] = 'attachment; filename=generated_xccdf.xml'
    response.headers['Content-type'] = 'text/plain'
    return response
