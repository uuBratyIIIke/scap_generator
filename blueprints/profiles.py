from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
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
