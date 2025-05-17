from flask import Flask, render_template, request, redirect, url_for
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
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = SQLAlchemy(app)

class Group(db.Model):
    __tablename__ = 'groups'  # Явно указываем имя таблицы
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    profiles = db.relationship('Profile', backref='group')
    def __repr__(self):
        return f'<Group {self.name}>'

class Parameter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, unique=True, nullable=False)
    value = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'))  # Внешний ключ    

    group = db.relationship('Group', backref='parameters')  # Связь для ORM
    
    def __repr__(self):
        return f'<Parameter {self.name}>'


class Profile(db.Model):
    __tablename__ = 'profile'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    is_selected = db.Column(db.Boolean, nullable=False, default=False)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'))  # Явный ForeignKey
    rule_id = db.Column(db.Integer, db.ForeignKey('parameter.id'))  # Явный ForeignKey
    severity = db.Column(db.String(64), nullable=False)
    title = db.Column(db.String(256))
    content_href = db.Column(db.String(512))

    # Явно указываем отношения
    rule = db.relationship('Parameter', backref='profiles')
    def __repr__(self):
        return f'<Profile {self.name}>'


# Создаем таблицы в контексте приложения
#for commit
with app.app_context():
    db.create_all()  # Создаём заново с новыми структурами    

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    parameters = Parameter.query.options(db.joinedload(Parameter.group)).all()
    return render_template('index.html', parameters=parameters)

@app.route('/add', methods=['GET', 'POST'])
def add_parameter():
    if request.method == 'POST':
        # Обработка обычной формы
        if 'name' in request.form:
            try:
                new_param = Parameter(
                    name=request.form['name'],
                    value=request.form['value'],
                    description=request.form.get('description', '')
                )
                db.session.add(new_param)
                db.session.commit()
                return redirect(url_for('index'))
            except Exception as e:
                db.session.rollback()
                return f"Ошибка при добавлении: {str(e)}", 400
        
        # Обработка загрузки файла
        if 'csv_file' in request.files:
            file = request.files['csv_file']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                file.save(filepath)
                
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        csv_reader = csv.DictReader(f, delimiter=',')
                        for row in csv_reader:
                            param = Parameter(
                                name=row['name'],
                                value=row.get('value', ''),
                                description=row.get('description', '')
                            )
                            db.session.add(param)
                        db.session.commit()
                    return redirect(url_for('index'))
                except Exception as e:
                    db.session.rollback()
                    return f"Ошибка при импорте CSV: {str(e)}", 400
                finally:
                    if os.path.exists(filepath):
                        os.remove(filepath)
    
    return render_template('add.html')

@app.route('/delete/<int:id>')
def delete_parameter(id):
    parameter_to_delete = Parameter.query.get_or_404(id)
    db.session.delete(parameter_to_delete)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_parameter(id):
    parameter = Parameter.query.get_or_404(id)
    groups = Group.query.all()
    if request.method == 'POST':
        parameter.name = request.form['name']
        parameter.value = request.form['value']
        parameter.description = request.form['description']
        parameter.group_id = request.form.get('group_id') or None
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('edit.html', parameter=parameter, groups=groups)

@app.route('/export')
def export_to_file():
    # Получаем все параметры из базы
    parameters = Parameter.query.all()
    file_content = ""
    
    #Формируем блок defenitions
    file_content += "<definitions>\n" 

    for param in parameters:
        file_content += f"""
    <definition id=\"oval:custom:def:{param.id}\" version=\"1\" class=\"compliance\">
        <metadata>
            <title>___</title>
            <description>___</description>
        </metadata>
        <criteria>
            <criterion test_ref=\"oval:custom:tst:{param.id}\"/>
        </criteria>
    </definition>\n\n"""
   
    file_content += "</definitions>\n\n"
    
    # Формируем блок tests
    file_content += "<tests>\n"
    for param in parameters:
        file_content += f"""
    <ind:textfilecontent54_test id=\"oval:custom:tst:{param.id}\" version=\"1\" check=\"all\"  comment=\"____\">
      <ind:object object_ref=\"oval:custom:obj:{param.id}\" />
      <ind:state state_ref=\"oval:custom:ste:{param.id}\" />
    </ind:textfilecontent54_test>\n\n"""
    
    file_content += "</tests>\n\n"
    
    # Формируем блок objects
    file_content += "<objects>\n"

    for param in parameters:
        file_content += f"""
    <ind:textfilecontent54_object id=\"oval:custom:obj:{param.id}\" version=\"1\">
        <ind:filepath>/mnt/d/Studying/Pg_conf_file/pg_conf_file_04/postgresql.conf</ind:filepath>
        <ind:pattern operation=\"pattern match\">{param.name}=\s*'{param.value}'?</ind:pattern>
        <ind:instance datatype=\"int\" operation=\"greater than or equal\">1</ind:instance>
    </ind:textfilecontent54_object>\n\n"""

    file_content += "</objects>\n\n"

    # Формируем блок states
    file_content += "<states>\n"

    for param in parameters:
        file_content += f"""
    <ind:textfilecontent54_state id=\"oval:custom:ste:{param.id}\" version=\"1\">
        <ind:text operation=\"pattern match\">{param.value}'?</ind:text>
    </ind:textfilecontent54_state>\n\n"""

    file_content += "</states>"

    # Создаем ответ с файлом
    response = make_response(file_content)
    response.headers['Content-Disposition'] = 'attachment; filename=parameters_export.xml'
    response.headers['Content-type'] = 'text/plain'
    
    return response


@app.route('/profiles', methods=['GET', 'POST'])
def profiles():
    if request.method == 'POST':
        # Обработка добавления нового профиля
        name = request.form.get('name')
        description = request.form.get('description')
        is_selected = True if request.form.get('is_selected') else False
        group_id = request.form.get('group_id')
        rule_id = request.form.get('rule_id')
        severity = request.form.get('severity')
        title = request.form.get('title')
        content_href = request.form.get('content_href')

        new_profile = Profile(
            name=name,
            description=description,
            is_selected=is_selected,
            group_id=group_id,
            rule_id=rule_id,
            severity=severity,
            title=title,
            content_href=content_href
        )
        db.session.add(new_profile)
        db.session.commit()
        return redirect(url_for('profiles'))

    # Получение данных для страницы
    all_profiles = Profile.query.all()
    groups = Group.query.all()
    parameters = Parameter.query.all()
    return render_template('profiles.html', profiles=all_profiles, groups=groups, parameters=parameters)

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

    # Формируем содержимое файла
    file_content = "ID|Name|Value|Group|Description\n"  # Заголовки
    for param, group_name in parameters:
        file_content += f"{param.id}|{param.name}|{param.value}|{group_name or 'No group'}|{param.description or ''}\n"
    
    # Создаем ответ с файлом
    response = make_response(file_content)
    response.headers['Content-Disposition'] = 'attachment; filename=parameters_export.xccdf'
    response.headers['Content-type'] = 'text/plain'
    
    return response
    
    parameters = Parameter.query.options(db.joinedload(Parameter.group)).all()
    file_content = ""

    for param in parameters:
        if(not param.group.name):
            continue 
        file_content += f"""
<Group id="xccdf_org.postgresql_group_{param.id}">
"""

    '''
    <Group id="xccdf_org.postgresql_group_{param.group.name}">
        <title>SSL Configuration Group</title>
        <description>Проверки SSL-параметров</description>

        <!-- Правила -->
        <Rule id="xccdf_org.postgresql_rule_ssl_enabled" severity="high">
            <title>SSL должен быть включён</title>
            <check system="http://oval.mitre.org/XMLSchema/oval-definitions-5">
                <check-content-ref href="check_postgresql_ssl.xml" name="oval:ssl:def:1"/>
            </check>
        </Rule>
		
		 <Rule id="xccdf_org.postgresql_rule_ssl_prefer_server_ciphers" severity="high">
            <title>Использовать серверные шифры по умолчанию</title>
            <check system="http://oval.mitre.org/XMLSchema/oval-definitions-5">
                <check-content-ref href="check_postgresql_ssl.xml" name="oval:ssl:def:2"/>
            </check>
        </Rule>
		
		<Rule id="xccdf_org.postgresql_rule_ssl_min_protocol_version" severity="high">
            <title>Минимальная версия TLS - 1.2</title>
            <check system="http://oval.mitre.org/XMLSchema/oval-definitions-5">
                <check-content-ref href="check_postgresql_ssl.xml" name="oval:ssl:def:3"/>
            </check>
        </Rule>
    </Group>
    '''
if __name__ == '__main__':
    app.run(debug=True, port=5000)