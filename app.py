from enum import Enum

from flask import Flask, render_template, request, redirect, url_for, flash, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from flask import make_response
import csv
from io import TextIOWrapper
from werkzeug.utils import secure_filename
import os

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv'}

app = Flask(__name__)
# Конфигурация для MySQL
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://admin:admin@localhost/safety_checker_new?charset=utf8mb4'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

db = SQLAlchemy(app)

class OperationEnum(str, Enum):
    EQUALS = "equals"
    NOT_EQUAL = "not equal"
    GREATER_THAN = "greater than"
    LESS_THAN = "less than"
    PATTERN_MATCH = "pattern match"

class Group(db.Model):
    __tablename__ = 'groups'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # Явно указываем autoincrement
    name = db.Column(db.String(100), unique=True, nullable=False)
    
    # Для MySQL может потребоваться указать длину индекса
    __table_args__ = (
        db.Index('ix_groups_name', name, mysql_length=100),
        {'mysql_engine': 'InnoDB'}  # Указываем движок для MySQL
    )
    
    profiles = db.relationship('Profile', backref='group')
    
    def __repr__(self):
        return f'<Group {self.name}>'


class Parameter(db.Model):
    __tablename__ = 'parameter'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # Явно указываем autoincrement
    name = db.Column(db.String(255), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'))
    
    __table_args__ = (
        db.Index('ix_parameters_name', name, mysql_length=255),
        {'mysql_engine': 'InnoDB'}
    )
    
    group = db.relationship('Group', backref='parameter')
    
    def __repr__(self):
        return f'<Parameter {self.name}>'

class Profile(db.Model):
    __tablename__ = 'profile'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # Явно указываем autoincrement
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    is_selected = db.Column(db.Boolean, nullable=False, default=False)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'))
    rule_id = db.Column(db.Integer)
    severity = db.Column(db.String(64), nullable=False)
    title = db.Column(db.String(256))
    content_href = db.Column(db.String(512))
    
    __table_args__ = {'mysql_engine': 'InnoDB'}
    
    #rule = db.relationship('Parameter', backref='profiles')
    
    def __repr__(self):
        return f'<Profile {self.name}>'

# Создаем таблицы в контексте приложения
#with app.app_context():
#    db.create_all()  # Создаём таблицы, если они не существуют  

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    parameters = Parameter.query.all()
    groups = Group.query.all()
    return render_template('index.html', parameters=parameters, groups=groups)

@app.route('/add', methods=['GET', 'POST'])
def add_parameter():
    all_groups = Group.query.order_by(Group.name).all()
    operations = list(OperationEnum)

    if request.method == 'POST':
        # Обработка обычной формы
        if 'name' in request.form:
            try:
                operation = OperationEnum(request.form["operation"])
                new_param = Parameter(
                    name=request.form['name'],
                    value=request.form['value'],
                    description=request.form.get('description', ''),
                    comment=request.form.get('comment', ''),    # НОВОЕ ПОЛЕ
                    title=request.form.get('title', ''),        # НОВОЕ ПОЛЕ
                    group_id=request.form.get('group_id') or None,
                    operation=operation
                )
                db.session.add(new_param)
                db.session.commit()
                flash('Параметр успешно добавлен', 'success')
                return redirect(url_for('index'))
            except ValueError:
                flash('Недопустимое значение операции', 'error')
            except Exception as e:
                db.session.rollback()
                flash(f'Ошибка при добавлении: {str(e)}', 'error')

        # Обработка загрузки CSV
        elif 'csv_file' in request.files:
            file = request.files['csv_file']
            if file and allowed_file(file.filename):
                try:
                    # Читаем CSV файл
                    stream = TextIOWrapper(file.stream._file, 'UTF-8')
                    csv_reader = csv.DictReader(stream, delimiter=',')

                    # Обрабатываем каждую строку
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
                            group_id=group_id
                        )
                        db.session.add(new_param)

                    db.session.commit()
                    flash('Параметры успешно импортированы', 'success')
                    return redirect(url_for('index'))

                except Exception as e:
                    db.session.rollback()
                    flash(f'Ошибка при импорте CSV: {str(e)}', 'error')
    
    return render_template("add.html", groups=all_groups, operations=operations)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'csv'

@app.route('/change_parameter_group/<int:param_id>', methods=['POST'])
def change_parameter_group(param_id):
    group_id = request.form.get('group_id') or None
    param = Parameter.query.get_or_404(param_id)
    param.group_id = group_id
    db.session.commit()
    flash('Группа параметра обновлена', 'success')
    return redirect(request.referrer or url_for('index'))

@app.route('/download_template')
def download_template():
    # Создаем CSV шаблон в памяти
    csv_data = "name,value,description,group\n"
    csv_data += "timeout,30,Таймаут соединения,Network\n"

    response = make_response(csv_data)
    response.headers['Content-Disposition'] = 'attachment; filename=parameters_template.csv'
    response.headers['Content-type'] = 'text/csv'
    return response

@app.route('/delete/<int:id>')
def delete_parameter(id):
    parameter_to_delete = Parameter.query.get_or_404(id)
    db.session.delete(parameter_to_delete)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_parameter(id):
    parameter = Parameter.query.get_or_404(id)
    all_groups = Group.query.order_by(Group.name).all()  # Получаем все группы с сортировкой
    operations = list(OperationEnum)  # Или другой источник данных

    if request.method == 'POST':

        if not request.form['name'] or not request.form['value']:
            flash('Название и значение обязательны для заполнения', 'error')
            return render_template('edit.html', parameter=parameter, groups=all_groups)

        parameter.name = request.form['name']
        parameter.value = request.form['value']
        parameter.description = request.form.get('description', '')
        parameter.group_id = request.form.get('group_id') or None  # Обрабатываем пустое значение
        parameter.operation = request.form.get('operation', '')
        db.session.commit()
        return redirect(url_for('index'))

    return render_template('edit.html', parameter=parameter, groups=all_groups, operations=operations)

@app.route('/export', methods=['POST', 'GET'])
def export_to_file():
    selected_ids = request.form.getlist('selected_ids')

    # Получаем только выбранные параметры
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
    
    #Формируем блок defenitions
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
    
    # Формируем блок tests
    file_content += "<tests>\n"
    for param, group_name in parameters:
        file_content += f"""
    <ind:textfilecontent54_test id=\"oval:{group_name or "custom"}:tst:{param.id}\" version=\"1\" check=\"all\"  comment=\"{param.comment}\">
      <ind:object object_ref=\"oval:{group_name or "custom"}:obj:{param.id}\" />
      <ind:state state_ref=\"oval:{group_name or "custom"}:ste:{param.id}\" />
    </ind:textfilecontent54_test>\n\n"""
    
    file_content += "</tests>\n\n"
    
    # Формируем блок objects
    file_content += "<objects>\n"

    for param, group_name in parameters:
        file_content += f"""
    <ind:textfilecontent54_object id=\"oval:{group_name or "custom"}:obj:{param.id}\" version=\"1\">
        <ind:filepath>/mnt/d/Studying/Pg_conf_file/pg_conf_file_04/postgresql.conf</ind:filepath>
        <ind:pattern operation=\"pattern match\">^{param.name}\s*=\s*'?(\w+)'?</ind:pattern>
        <ind:instance datatype=\"int\" operation=\"greater than or equal\">1</ind:instance>
    </ind:textfilecontent54_object>\n\n"""

    file_content += "</objects>\n\n"

    # Формируем блок states
    file_content += "<states>\n"

    for param, group_name in parameters:
        file_content += f"""
    <ind:textfilecontent54_state id=\"oval:{group_name or "custom"}:ste:{param.id}\" version=\"1\">
        <ind:text operation=\"{param.operation}\">^{param.name}\s*=\s*'?({param.value})'?</ind:text>
    </ind:textfilecontent54_state>\n\n"""

    file_content += "</states> </oval_definitions>"

    # Создаем ответ с файлом
    response = make_response(file_content)
    response.headers['Content-Disposition'] = 'attachment; filename=generated_xccdf.xml'
    response.headers['Content-type'] = 'text/plain'

    return response


# Маршруты для работы с профилями
@app.route('/profiles')
def profiles():
    profiles = Profile.query.all()
    return render_template('profiles.html', profiles=profiles)

@app.route('/profiles/add', methods=['GET', 'POST'])
def add_profile():
    if request.method == 'POST':
        try:
            profile = Profile(
                name=request.form['name'],
                description=request.form.get('description'),
                is_selected='is_selected' in request.form,
                group_id=request.form.get('group_id'),
                rule_id=request.form.get('rule_id'),
                severity=request.form['severity'],
                title=request.form.get('title'),
                content_href=request.form.get('content_href')
            )
            db.session.add(profile)
            db.session.commit()
            flash('Профиль успешно добавлен', 'success')
            return redirect(url_for('profiles'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при добавлении профиля: {str(e)}', 'error')
    
    groups = Group.query.all()
    parameters = Parameter.query.all()
    return render_template('add_profile.html', 
                         groups=groups,
                         parameters=parameters)

@app.route('/profiles/edit/<int:id>', methods=['GET', 'POST'])
def edit_profile(id):
    profile = Profile.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            profile.name = request.form['name']
            profile.description = request.form.get('description')
            profile.is_selected = 'is_selected' in request.form
            profile.group_id = request.form.get('group_id')
            profile.rule_id = request.form.get('rule_id')
            profile.severity = request.form['severity']
            profile.title = request.form.get('title')
            profile.content_href = request.form.get('content_href')
            
            db.session.commit()
            flash('Профиль успешно обновлен', 'success')
            return redirect(url_for('profiles'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении профиля: {str(e)}', 'error')
    
    groups = Group.query.all()
    parameters = Parameter.query.all()
    return render_template('edit_profile.html', 
                         profile=profile,
                         groups=groups,
                         parameters=parameters)


@app.route('/profiles/delete/<int:id>')
def delete_profile(id):
    try:
        profile = Profile.query.get_or_404(id)
        db.session.delete(profile)
        db.session.commit()
        flash('Профиль успешно удален', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении профиля: {str(e)}', 'error')
    return redirect(url_for('profiles'))

@app.route('/groups', methods=['GET', 'POST'])
def groups():
    if request.method == 'POST':
        group_name = request.form.get('group_name')
        if group_name:
            new_group = Group(name=group_name)
            db.session.add(new_group)
            db.session.commit()
            return redirect(url_for('groups'))
    all_groups = Group.query.all()
    return render_template('groups.html', groups=all_groups)

@app.route('/add_group', methods=['GET', 'POST'])
def add_group():
    if request.method == 'POST':
        group_name = request.form['name']
        new_group = Group(name=group_name)
        db.session.add(new_group)
        db.session.commit()
        return redirect(url_for('groups'))
    return render_template('add_group.html')

@app.route('/delete_group/<int:id>')
def delete_group(id):
    group_to_delete = Group.query.get_or_404(id)
    # Удаляем или обнуляем связанные параметры
    Parameter.query.filter_by(group_id=id).update({'group_id': None})
    db.session.delete(group_to_delete)
    db.session.commit()
    return redirect(url_for('groups'))

@app.route('/export_xccdf')
def export_to_xccdf_file():
    # Получаем все параметры с именами групп
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


    # Создаем ответ с файлом
    response = make_response(file_content)
    response.headers['Content-Disposition'] = 'attachment; filename=benchmark_xccdf.xml'
    response.headers['Content-type'] = 'text/plain'

    return response

if __name__ == '__main__':
    app.run(debug=True, port=5000)