@app.route('/export')
def export_to_file():
    # Получаем все параметры из базы
    parameters = Parameter.query.all()
    file_content = ""
    
    #Формируем блок defenitions
    file_content += "<defenitions>\n" 

    for param in parameters:
        file_content += f"""
    <definition id=\"oval:custom:def:{param.id}\" version=\"1\" class=\"compliance\">
        <metadata>
            <title>___</title>
            <description>___<description>
        </metadata>
        <criteria>
            <criterion test_ref=\"oval:custom:tst:{param.id}\"/>
        </criteria>
    </definition>\n\n"""
   
    file_content += "</defenitions>\n\n"
    
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
        <ind:text operation=\"pattern match\">ssl\s*=\s*'?(on|true)'?</ind:text>
    </ind:textfilecontent54_state>\n\n"""

    file_content += "</states>"

    # Создаем ответ с файлом
    response = make_response(file_content)
    response.headers['Content-Disposition'] = 'attachment; filename=parameters_export.xml'
    response.headers['Content-type'] = 'text/plain'
    
    return response