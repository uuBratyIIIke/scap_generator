from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from flask import make_response

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
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
    
@app.route('/')
def index():
    parameters = Parameter.query.all()  # Исправлено: Parameter вместо parameters
    return render_template('index.html', parameters=parameters)

@app.route('/add', methods=['GET', 'POST'])
def add_parameter():
    if request.method == 'POST':
        try:
            new_param = Parameter(
                name=request.form['name'],
                value=request.form['value'],
                description=request.form.get('description', '')  # description необязателен
            )
            db.session.add(new_param)
            db.session.commit()
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            return f"Ошибка при добавлении: {str(e)}", 400
    
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
    
    # Формируем содержимое файла
    file_content = ""
    for param in parameters:
        file_content += f"""
<ind:textfilecontent54_object id=\"oval:ssl:obj:{param.id}\" version=\"1\">
  <ind:filepath>/mnt/d/Studying/Pg_conf_file/pg_conf_file_04/postgresql.conf</ind:filepath>
  <ind:pattern operation=\"pattern match\">{param.name}=\s*'{param.value}'?</ind:pattern>
  <ind:instance datatype=\"int\" operation=\"greater than or equal\">1</ind:instance>
</ind:textfilecontent54_object>\n\n"""

    # Создаем ответ с файлом
    response = make_response(file_content)
    response.headers['Content-Disposition'] = 'attachment; filename=parameters_export.txt'
    response.headers['Content-type'] = 'text/plain'
    
    return response

if __name__ == '__main__':
    app.run(debug=True, port=5000)