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

class Parameter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, unique=True, nullable=False)
    value = db.Column(db.Text, unique=False, nullable=False)
    description = db.Column(db.Text, unique=False, nullable=True)  # Исправлено: db.Column
    
    def __repr__(self):
        return f'<Parameter {self.name}>'  # Исправлено: используем self.name

# Создаем таблицы в контексте приложения
#for commit
with app.app_context():
    db.create_all()
    

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    parameters = Parameter.query.all()  # Исправлено: Parameter вместо parameters
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
    if request.method == 'POST':
        parameter.name = request.form['name']
        parameter.value = request.form['value']
        parameter.description = request.form['description']
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('edit.html', parameter=parameter)

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

if __name__ == '__main__':
    app.run(debug=True, port=5000)