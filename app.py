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
    all_groups = Group.query.order_by(Group.name).all()
    
    if request.method == 'POST':
        # Обработка обычной формы
        if 'name' in request.form:
            try:
                new_param = Parameter(
                    name=request.form['name'],
                    value=request.form['value'],
                    description=request.form.get('description', ''),
                    group_id=request.form.get('group_id') or None
                )
                db.session.add(new_param)
                db.session.commit()
                flash('Параметр успешно добавлен', 'success')
                return redirect(url_for('index'))
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
    
    return render_template('add.html', groups=all_groups)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'csv'

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
    
    if request.method == 'POST':
   
        if not request.form['name'] or not request.form['value']:
            flash('Название и значение обязательны для заполнения', 'error')
            return render_template('edit.html', parameter=parameter, groups=all_groups)
        
        parameter.name = request.form['name']
        parameter.value = request.form['value']
        parameter.description = request.form.get('description', '')
        parameter.group_id = request.form.get('group_id') or None  # Обрабатываем пустое значение
        db.session.commit()
        return redirect(url_for('index'))
    
    return render_template('edit.html', parameter=parameter, groups=all_groups)

@app.route('/export', methods=['POST'])
def export_to_file():
    selected_ids = request.form.get('selected_ids', '').split(',')
    
    # Получаем только выбранные параметры
    parameters = db.session.query(
        Parameter,
        Group.name.label('group_name')
    ).outerjoin(
        Group, Parameter.group_id == Group.id
    ).filter(
        Parameter.id.in_(selected_ids)
    ).all()

    file_content = ""
    
    #Формируем блок defenitions
    file_content += "<definitions>\n" 

    for param, group_name in parameters:
        file_content += f"""
    <definition id=\"oval:{group_name or "custom"}:def:{param.id}\" version=\"1\" class=\"compliance\">
        <metadata>
            <title>___</title>
            <description>___</description>
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
    <ind:textfilecontent54_test id=\"oval:{group_name or "custom"}:tst:{param.id}\" version=\"1\" check=\"all\"  comment=\"____\">
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
        <ind:pattern operation=\"pattern match\">{param.name}=\s*'{param.value}'?</ind:pattern>
        <ind:instance datatype=\"int\" operation=\"greater than or equal\">1</ind:instance>
    </ind:textfilecontent54_object>\n\n"""

    file_content += "</objects>\n\n"

    # Формируем блок states
    file_content += "<states>\n"

    for param, group_name in parameters:
        file_content += f"""
    <ind:textfilecontent54_state id=\"oval:{group_name or "custom"}:ste:{param.id}\" version=\"1\">
        <ind:text operation=\"pattern match\">{param.value}'?</ind:text>
    </ind:textfilecontent54_state>\n\n"""

    file_content += "</states>"

    # Создаем ответ с файлом
    response = make_response(file_content)
    response.headers['Content-Disposition'] = 'attachment; filename=parameters_export.xml'
    response.headers['Content-type'] = 'text/plain'
    
    return response

@app.route('/groups')
def groups():
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
            <check-content-ref href=\"check_postgresql_ssl.xml\" name=\"oval:{group.name or "custom"}:def:{param.Parameter.id}\"/>
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