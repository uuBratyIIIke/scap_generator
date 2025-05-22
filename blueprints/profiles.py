from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, make_response
from models import db, Group, Parameter, Profile

profiles_bp = Blueprint('profiles', __name__, url_prefix='/profiles')

@profiles_bp.route('/')
def list_profiles():
    profiles = Profile.query.all()
    groups = Group.query.all()
    return render_template('profiles.html', profiles=profiles, groups=groups)

@profiles_bp.route('/update_profile_groups', methods=['POST'])
def update_profile_groups():
    data = request.get_json()
    profile_id = data.get('profile_id')
    group_ids = data.get('group_ids', [])
    profile = Profile.query.get(profile_id)
    if not profile:
        return jsonify({'success': False, 'error': 'Профиль не найден'}), 404
    profile.groups = Group.query.filter(Group.id.in_(group_ids)).all()
    db.session.commit()
    return jsonify({'success': True})

@profiles_bp.route('/add', methods=['GET', 'POST'])
def add_profile():
    if request.method == 'POST':
        try:
            profile = Profile(
                name=request.form['name'],
                description=request.form.get('description'),
                is_selected='is_selected' in request.form,
                severity=request.form['severity'],
                title=request.form.get('title'),
                content_href=request.form.get('content_href')
            )
            db.session.add(profile)
            db.session.commit()
            flash('Профиль успешно добавлен', 'success')
            return redirect(url_for('profiles.list_profiles'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при добавлении профиля: {str(e)}', 'error')
    groups = Group.query.all()
    parameters = Parameter.query.all()
    return render_template('add_profile.html', groups=groups, parameters=parameters)

@profiles_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_profile(id):
    profile = Profile.query.get_or_404(id)
    if request.method == 'POST':
        try:
            profile.name = request.form['name']
            profile.description = request.form.get('description')
            profile.is_selected = 'is_selected' in request.form
            profile.severity = request.form['severity']
            profile.title = request.form.get('title')
            profile.content_href = request.form.get('content_href')

            # --- ВАЖНО: обновление групп ---
            group_ids = request.form.getlist('group_ids')
            profile.groups = Group.query.filter(Group.id.in_(group_ids)).all()

            db.session.commit()
            flash('Профиль успешно обновлен', 'success')
            return redirect(url_for('profiles.list_profiles'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении профиля: {str(e)}', 'error')
    groups = Group.query.all()
    parameters = Parameter.query.all()
    return render_template('edit_profile.html', profile=profile, groups=groups, parameters=parameters)

@profiles_bp.route('/delete/<int:id>')
def delete_profile(id):
    try:
        profile = Profile.query.get_or_404(id)
        db.session.delete(profile)
        db.session.commit()
        flash('Профиль успешно удален', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении профиля: {str(e)}', 'error')
    return redirect(url_for('profiles.list_profiles'))


@profiles_bp.route('/export', methods=['POST'])
def export_profiles():
    selected_ids = request.form.getlist('selected_profile_ids')
    if not selected_ids:
        flash('Не выбрано ни одного профиля для экспорта!', 'warning')
        return redirect(url_for('profiles.list_profiles'))

    profiles = Profile.query.filter(Profile.id.in_(selected_ids)).all()
    parameters = db.session.query(
        Parameter,
        Group.name.label('group_name')
    ).outerjoin(
        Group, Parameter.group_id == Group.id
    ).all()

    groups = set()

    file_content = """<Benchmark 
    xmlns="http://checklists.nist.gov/xccdf/1.2" 
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://checklists.nist.gov/xccdf/1.2 https://nvd.nist.gov/schema/xccdf-1.2.xsd"
    id="xccdf_org.postgresql_benchmark_1.0">
    
    <!-- Обязательные элементы в правильном порядке -->
    <status date="2024-05-25">draft</status>
    <title>PostgreSQL Security Benchmark</title>
    <description>Проверка безопасности PostgreSQL</description>
    <version>1.0</version>
    """

    for profile in profiles:
        file_content += f"""
        <Profile id="xccdf_org.postgresql_profile_{profile.name}">
	        <title>{profile.title}</title>
	        <description>{profile.description}</description>"""
        for group in profile.groups:
            groups.add(group)
            file_content += f"""
            <select idref="xccdf_org.postgresql_group_{group.name}" selected="true"/>"""

        file_content += """
        </Profile>\n"""

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
        file_content += "</Group>\n"

    file_content += "\n\n</Benchmark>"

    response = make_response(file_content)
    response.headers['Content-Disposition'] = 'attachment; filename=benchmark_xccdf.xml'
    response.headers['Content-type'] = 'text/plain'
    return response