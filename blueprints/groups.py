from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Group, Parameter

groups_bp = Blueprint('groups', __name__, url_prefix='/groups')


@groups_bp.route('/', methods=['GET', 'POST'])
def list_groups():
    if request.method == 'POST':
        group_name = request.form.get('group_name')
        if group_name:
            new_group = Group(name=group_name)
            db.session.add(new_group)
            db.session.commit()
            flash('Группа успешно добавлена', 'success')
            return redirect(url_for('groups.list_groups'))
    all_groups = Group.query.all()
    return render_template('groups.html', groups=all_groups)


@groups_bp.route('/add', methods=['GET', 'POST'])
def add_group():
    if request.method == 'POST':
        group_name = request.form['name']
        new_group = Group(name=group_name)
        db.session.add(new_group)
        db.session.commit()
        flash('Группа успешно добавлена', 'success')
        return redirect(url_for('groups.list_groups'))
    return render_template('add_group.html')


@groups_bp.route('/delete/<int:id>')
def delete_group(id):
    group_to_delete = Group.query.get_or_404(id)
    Parameter.query.filter_by(group_id=id).update({'group_id': None})
    db.session.delete(group_to_delete)
    db.session.commit()
    flash('Группа успешно удалена', 'success')
    return redirect(url_for('groups.list_groups'))


@groups_bp.route('/export_xccdf')
def export_to_xccdf_file():
    from models import Parameter  # Импортируем здесь, чтобы избежать циклических импортов
    parameters = db.session.query(
        Parameter,
        Group.name.label('group_name')
    ).outerjoin(
        Group, Parameter.group_id == Group.id
    ).all()
    groups = db.session.query(Group)
    file_content = ""
    for group in groups:
        file_content += f"""
    <Group id="xccdf_org.postgresql_group_{group.name}">
        <title>{group.name} Configuration Group</title>
        <description>Проверки {group.name} </description>

        <!-- Правила -->
    """
        for param in parameters:
            if param.Parameter.group_id == group.id:
                file_content += f"""
    <Rule id=\"xccdf_org.postgresql_rule_{param.Parameter.name}\" severity=\"high\">
        <title>{param.Parameter.description}</title>
        <check system="http://oval.mitre.org/XMLSchema/oval-definitions-5">
            <check-content-ref href=\"generated_oval.xml\" name=\"oval:{group.name or "custom"}:def:{param.Parameter.id}\"/>
        </check>
    </Rule>\n
"""
        file_content += "   </Group>"
    from flask import make_response
    response = make_response(file_content)
    response.headers['Content-Disposition'] = 'attachment; filename=benchmark_xccdf.xml'
    response.headers['Content-type'] = 'text/plain'
    return response
